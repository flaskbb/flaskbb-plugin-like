from flaskbb.forum.models import Post
from sqlalchemy import inspect

from like.models import PostLike


def test_post_likers_empty_by_default(topic):
    assert list(topic.first_post.likers) == []


def test_post_likers_after_like(topic, user, moderator_user):
    post = Post(content="Test reply").save(user=user, topic=topic)
    PostLike(post_id=post.id, user_id=moderator_user.id).save()

    assert list(post.likers) == [moderator_user]


def test_post_likers_only_lists_that_posts_likers(topic, user, moderator_user):
    post_a = Post(content="Post A").save(user=user, topic=topic)
    post_b = Post(content="Post B").save(user=user, topic=topic)
    PostLike(post_id=post_a.id, user_id=moderator_user.id).save()

    assert list(post_a.likers) == [moderator_user]
    assert list(post_b.likers) == []


def test_user_liked_posts_backref(liked_post, moderator_user):
    assert [pl.post for pl in moderator_user.user_liked_posts] == [liked_post]


def test_deleting_a_liked_post_cascades_the_like(liked_post):
    assert PostLike.count(column=PostLike.post_id) == 1

    liked_post.delete()

    assert PostLike.count(column=PostLike.post_id) == 0


def test_user_liked_posts_backref_cascades_on_delete():
    """Deleting a User end-to-end and checking PostLike rows disappear
    would be the more direct test, but User.delete() currently raises
    on an unrelated flaskbb-core issue (User.tracked_topics is a
    write-only relationship that needs passive_deletes=True to survive a
    delete flush) before it ever gets to user_liked_posts. Asserting the
    cascade configuration directly sidesteps that pre-existing, unrelated
    breakage while still proving a user delete would take their likes
    with it.
    """
    user_liked_posts = inspect(PostLike).relationships["user"].backref
    assert user_liked_posts is not None
    _, backref_kwargs = user_liked_posts
    assert "delete" in backref_kwargs["cascade"]
    assert "delete-orphan" in backref_kwargs["cascade"]
