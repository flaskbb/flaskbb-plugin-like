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


AJAX = {"X-Requested-With": "XMLHttpRequest"}


def _post(application, view_cls, endpoint_name, post_id, user, headers=None):
    view = view_cls.as_view(endpoint_name)
    with (
        _csrf_disabled(application),
        application.test_request_context(
            method="POST", path=f"/like/{post_id}/{endpoint_name}", headers=headers
        ),
    ):
        login_user(user)
        try:
            return view(post_id=post_id)
        finally:
            logout_user()


def _like(application, post, user, headers=None):
    return _post(application, LikePost, "like", post.id, user, headers)


def _unlike(application, post, user, headers=None):
    return _post(application, UnlikePost, "unlike", post.id, user, headers)


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


def test_like_post_ajax_returns_the_updated_widget(
    application, topic, user, moderator_user
):
    post = topic.first_post
    resp = _like(application, post, moderator_user, headers=AJAX)

    assert resp.status_code == 200
    data = resp.get_json()
    # The widget comes back in its unliked -> liked state: the button now
    # posts to unlike, and the count went up.
    assert f"/like/{post.id}/unlike" in data["widget"]
    assert "1 like" in data["widget"]

    counts = {entry["user_id"]: entry for entry in data["counts"]}
    assert counts[moderator_user.id]["given"] == 1
    assert counts[user.id]["received"] == 1


def test_unlike_post_ajax_returns_the_updated_widget(
    application, liked_post, user, moderator_user
):
    resp = _unlike(application, liked_post, moderator_user, headers=AJAX)

    assert resp.status_code == 200
    data = resp.get_json()
    assert f"/like/{liked_post.id}/like" in data["widget"]
    assert "0 likes" in data["widget"]

    counts = {entry["user_id"]: entry for entry in data["counts"]}
    assert counts[moderator_user.id]["given"] == 0
    assert counts[user.id]["received"] == 0


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
