from flask import g, url_for


def test_profile_shows_liked_posts_tab(application, default_settings, user):
    with application.test_request_context():
        profile_url = user.url
        liked_posts_url = url_for("like.liked_posts", username=user.username)

    # requests reuse the package-wide app context, so drop any user an
    # earlier test left in flask-login's g cache
    g.pop("_login_user", None)
    resp = application.test_client().get(profile_url)

    assert resp.status_code == 200
    assert f'href="{liked_posts_url}"'.encode() in resp.data
