import re
from contextlib import contextmanager

import pytest
from flask_login import login_user, logout_user
from flaskbb.forum.models import Post
from werkzeug.exceptions import Forbidden

import like
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


HTMX = {"HX-Request": "true"}


def _counts(html, user_id):
    """The out-of-band counts block for ``user_id`` in an htmx response, as
    ``(given, received)``."""
    match = re.search(
        rf"data-user-id=\"{user_id}\" "
        rf"hx-swap-oob=\"outerHTML:\.like-counts\[data-user-id='{user_id}'\]\">"
        r".*?like-counts-given\">(\d+)<.*?like-counts-received\">(\d+)<",
        html,
        re.S,
    )
    assert match is not None
    return int(match.group(1)), int(match.group(2))


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
    with application.test_request_context(method="POST", path=f"/like/{liked_post.id}/unlike"):
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


def test_like_post_htmx_returns_the_updated_widget(application, topic, user, moderator_user):
    post = topic.first_post
    resp = _like(application, post, moderator_user, headers=HTMX)

    # The widget comes back in its unliked -> liked state: the button now
    # posts to unlike, and the count went up.
    assert f'hx-post="/like/{post.id}/unlike"' in resp
    assert "1 like" in resp
    assert _counts(resp, moderator_user.id)[0] == 1
    assert _counts(resp, user.id)[1] == 1


def test_unlike_post_htmx_returns_the_updated_widget(application, liked_post, user, moderator_user):
    resp = _unlike(application, liked_post, moderator_user, headers=HTMX)

    assert f'hx-post="/like/{liked_post.id}/like"' in resp
    assert "0 likes" in resp
    assert _counts(resp, moderator_user.id)[0] == 0
    assert _counts(resp, user.id)[1] == 0


def test_htmx_like_of_an_already_liked_post_returns_its_current_state(
    application, liked_post, moderator_user
):
    """Liked from somewhere else in the meantime - the widget catches up
    instead of the request failing silently."""
    resp = _like(application, liked_post, moderator_user, headers=HTMX)

    assert f'hx-post="/like/{liked_post.id}/unlike"' in resp
    assert PostLike.count(column=PostLike.post_id) == 1


def test_htmx_like_with_an_invalid_token_loads_the_post(application, topic, moderator_user):
    post = topic.first_post
    headers = {
        "HX-Request": "true",
        "HX-Current-URL": f"http://localhost/topic/{topic.id}-{topic.slug}",
    }

    view = LikePost.as_view("like")
    with application.test_request_context(
        method="POST", path=f"/like/{post.id}/like", headers=headers
    ):
        login_user(moderator_user)
        try:
            resp = view(post_id=post.id)
        finally:
            logout_user()

    assert resp.status_code == 204
    assert resp.headers["HX-Redirect"] == f"/post/{post.id}"
    assert PostLike.count(column=PostLike.post_id) == 0


def test_page_counts_are_not_swapped_out_of_band(application, topic, user):
    with application.test_request_context():
        html = like.flaskbb_tpl_post_author_info_after(user, topic.first_post)

    assert 'class="like-counts"' in html
    assert "hx-swap-oob" not in html


def test_liked_posts_lists_only_that_users_likes(
    application, topic, user, moderator_user, admin_user
):
    liked = Post(content="Liked by moderator").save(user=user, topic=topic)
    not_liked = Post(content="Not liked").save(user=user, topic=topic)
    PostLike(post_id=liked.id, user_id=moderator_user.id).save()

    view = LikedPosts.as_view("liked_posts")
    with application.test_request_context(path=f"/like/{moderator_user.username}/liked-posts"):
        login_user(admin_user)
        try:
            resp = view(username=moderator_user.username)
        finally:
            logout_user()

    # render_template() returns a plain string when the view is called
    # directly like this, rather than through full request dispatch.
    assert liked.content in resp
    assert not_liked.content not in resp
