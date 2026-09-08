from flaskbb.settings import flaskbb_config
from flaskbb.extensions import db
from flaskbb.forum.models import Forum, Post, Topic
from sqlalchemy import event

from like.models import PostLike
from like.utils import (
    can_like_post,
    has_liked,
    like_post,
    likes_given_count,
    likes_received_count,
    recalculate_like_counts,
    unlike_post,
)


def test_can_like_post_allows_a_normal_post(topic, moderator_user):
    assert can_like_post(moderator_user, topic.first_post) is True


def test_can_like_post_rejects_own_post(topic, user):
    assert can_like_post(user, topic.first_post) is False


def test_can_like_post_rejects_locked_topic(topic_locked, moderator_user):
    assert can_like_post(moderator_user, topic_locked.first_post) is False


def test_can_like_post_rejects_locked_forum(topic_in_locked_forum, moderator_user):
    assert can_like_post(moderator_user, topic_in_locked_forum.first_post) is False


def test_can_like_post_rejects_user_outside_the_forums_groups(
    category, default_groups, user, moderator_user
):
    # Member only, deliberately excludes the Moderator group. Forum.save()
    # defaults groups=None to "every group" and overrides whatever
    # .groups was already set to, so the restriction has to go through
    # the save() argument, not plain attribute assignment.
    member_only_forum = Forum(title="Members Only", category_id=category.id)
    member_only_forum.save(groups=[default_groups[3]])

    other_topic = Topic(title="Members only topic")
    other_topic.save(
        forum=member_only_forum, user=user, post=Post(content="Members only content")
    )

    assert can_like_post(moderator_user, other_topic.first_post) is False


def test_can_like_post_allows_self_like_when_setting_enabled(
    topic, user, default_settings
):
    original = flaskbb_config["LIKE_ALLOW_SELF_LIKE"]
    flaskbb_config["LIKE_ALLOW_SELF_LIKE"] = True
    try:
        assert can_like_post(user, topic.first_post) is True
    finally:
        flaskbb_config["LIKE_ALLOW_SELF_LIKE"] = original


def test_like_post_creates_a_row(topic, moderator_user):
    post = topic.first_post
    like_post(moderator_user, post)

    assert has_liked(moderator_user, post) is True
    assert PostLike.count(column=PostLike.post_id) == 1


def test_unlike_post_removes_the_row(liked_post, moderator_user):
    assert has_liked(moderator_user, liked_post) is True

    unlike_post(moderator_user, liked_post)

    assert has_liked(moderator_user, liked_post) is False
    assert PostLike.count(column=PostLike.post_id) == 0


def test_unlike_post_is_a_noop_if_not_liked(topic, moderator_user):
    unlike_post(moderator_user, topic.first_post)

    assert PostLike.count(column=PostLike.post_id) == 0


def test_likes_given_count(topic, user, moderator_user):
    post_a = Post(content="A").save(user=user, topic=topic)
    post_b = Post(content="B").save(user=user, topic=topic)
    like_post(moderator_user, post_a)
    like_post(moderator_user, post_b)

    assert likes_given_count(moderator_user) == 2
    assert likes_given_count(user) == 0


def test_likes_received_count(topic, user, moderator_user):
    post_a = Post(content="A").save(user=user, topic=topic)
    post_b = Post(content="B").save(user=user, topic=topic)
    like_post(moderator_user, post_a)
    like_post(moderator_user, post_b)

    assert likes_received_count(user) == 2
    assert likes_received_count(moderator_user) == 0


def test_unlike_post_decrements_the_counters(liked_post, user, moderator_user):
    assert likes_given_count(moderator_user) == 1
    assert likes_received_count(user) == 1

    unlike_post(moderator_user, liked_post)

    assert likes_given_count(moderator_user) == 0
    assert likes_received_count(user) == 0


def test_deleting_a_liked_post_decrements_the_counters(
    liked_post, user, moderator_user
):
    """The cascade from Post -> PostLike goes through the ORM, so the
    counters have to follow it without like_post/unlike_post involved."""
    assert likes_given_count(moderator_user) == 1
    assert likes_received_count(user) == 1

    liked_post.delete()

    assert likes_given_count(moderator_user) == 0
    assert likes_received_count(user) == 0


def test_like_counts_cost_no_extra_queries(request_context, topic, moderator_user):
    """flaskbb_tpl_post_author_info_after fires once per post - a page with
    several posts by the same author must not re-query per post. The
    counters ride along on the already-loaded User row, so reading them
    emits nothing at all."""
    _ = moderator_user.likes_given  # force any cross-context lazy-refresh

    queries = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(db.engine, "before_cursor_execute", _count)
    try:
        for _ in range(5):
            likes_given_count(moderator_user)
            likes_received_count(moderator_user)
    finally:
        event.remove(db.engine, "before_cursor_execute", _count)

    assert queries == []


def test_recalculate_like_counts_repairs_drift(liked_post, user, moderator_user):
    # Simulated drift: a raw delete bypasses the ORM events that keep the
    # counters in sync.
    db.session.execute(db.delete(PostLike))
    db.session.commit()

    assert likes_given_count(moderator_user) == 1
    assert likes_received_count(user) == 1

    recalculate_like_counts(moderator_user)
    recalculate_like_counts(user)

    assert likes_given_count(moderator_user) == 0
    assert likes_received_count(user) == 0
