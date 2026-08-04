from contextlib import contextmanager

import pytest
from flask_login import login_user, logout_user
from flaskbb.forum.models import Post
from werkzeug.exceptions import Forbidden

from like.models import PostLike
from like.views import LikedPosts, LikePost, UnlikePost


@contextmanager
def _csrf_disabled(application):
    """LikePost/UnlikePost build a real LikeActionForm() to validate the
    request, which would otherwise reject a test-built POST for lacking a
    CSRF token - see tests/unit/forum/test_search_forms.py in flaskbb core
    for the same pattern.
    """
    original = application.config["WTF_CSRF_ENABLED"]
    application.config["WTF_CSRF_ENABLED"] = False
    try:
        yield
    finally:
        application.config["WTF_CSRF_ENABLED"] = original


def _post(application, view_cls, endpoint_name, post_id, user):
    view = view_cls.as_view(endpoint_name)
    with (
        _csrf_disabled(application),
        application.test_request_context(
            method="POST", path=f"/like/{post_id}/{endpoint_name}"
        ),
    ):
        login_user(user)
        try:
            return view(post_id=post_id)
        finally:
            logout_user()


def _like(application, post, user):
    return _post(application, LikePost, "like", post.id, user)


def _unlike(application, post, user):
    return _post(application, UnlikePost, "unlike", post.id, user)


def test_like_post_requires_login(application, topic):
    view = LikePost.as_view("like")
    post_id = topic.first_post.id
    with application.test_request_context(method="POST", path=f"/like/{post_id}/like"):
        resp = view(post_id=post_id)
    assert resp.status_code == 302
    assert PostLike.count(column=PostLike.post_id) == 0


def test_like_post_records_a_like(application, topic, moderator_user):
    post = topic.first_post
    resp = _like(application, post, moderator_user)

    assert resp.status_code == 302
    assert PostLike.count(column=PostLike.post_id) == 1


def test_like_post_rejects_own_post(application, topic, user):
    with pytest.raises(Forbidden):
        _like(application, topic.first_post, user)
    assert PostLike.count(column=PostLike.post_id) == 0


def test_like_post_rejects_a_second_like(application, liked_post, moderator_user):
    assert PostLike.count(column=PostLike.post_id) == 1
    with pytest.raises(Forbidden):
        _like(application, liked_post, moderator_user)
    assert PostLike.count(column=PostLike.post_id) == 1


def test_unlike_post_requires_login(application, liked_post):
    view = UnlikePost.as_view("unlike")
    with application.test_request_context(
        method="POST", path=f"/like/{liked_post.id}/unlike"
    ):
        resp = view(post_id=liked_post.id)
    assert resp.status_code == 302
    assert PostLike.count(column=PostLike.post_id) == 1


def test_unlike_post_removes_the_like(application, liked_post, moderator_user):
    resp = _unlike(application, liked_post, moderator_user)

    assert resp.status_code == 302
    assert PostLike.count(column=PostLike.post_id) == 0


def test_unlike_post_rejects_when_not_liked(application, topic, moderator_user):
    with pytest.raises(Forbidden):
        _unlike(application, topic.first_post, moderator_user)


def test_liked_posts_lists_only_that_users_likes(
    application, topic, user, moderator_user, admin_user
):
    liked = Post(content="Liked by moderator").save(user=user, topic=topic)
    not_liked = Post(content="Not liked").save(user=user, topic=topic)
    PostLike(post_id=liked.id, user_id=moderator_user.id).save()

    view = LikedPosts.as_view("liked_posts")
    with application.test_request_context(
        path=f"/like/{moderator_user.username}/liked-posts"
    ):
        login_user(admin_user)
        try:
            resp = view(username=moderator_user.username)
        finally:
            logout_user()

    # render_template() returns a plain string when the view is called
    # directly like this, rather than through full request dispatch.
    assert liked.content in resp
    assert not_liked.content not in resp
