"""
like
~~~~

Like functionality for FlaskBB. Lets users like posts and see who liked
them, via a button on the post menu.

:copyright: (c) 2026 by Peter Justin, (c) 2018 by Михаил Лебедев.
:license: BSD License, see LICENSE for more details.
"""

import os

from flask import Flask
from flask_babelplus import gettext as _
from flask_login import current_user
from flaskbb.settings import BoolSetting, SettingGroup
from flaskbb.display.navigation import NavigationLink
from flaskbb.forum.models import Post
from flaskbb.user.models import User
from flaskbb.utils.helpers import real, render_template
from pluggy import HookimplMarker

from .forms import LikeActionForm
from .utils import (
    DEFAULT_ALLOW_SELF_LIKE,
    can_like_post,
    has_liked,
    likes_given_count,
    likes_received_count,
)
from .views import like_bp

__version__ = "1.0.0"

hookimpl = HookimplMarker("flaskbb")


@hookimpl
def flaskbb_load_migrations():
    return os.path.join(os.path.dirname(__file__), "migrations")


@hookimpl
def flaskbb_load_translations():
    return os.path.join(os.path.dirname(__file__), "translations")


@hookimpl
def flaskbb_load_blueprints(app: Flask):
    app.register_blueprint(
        like_bp, url_prefix=app.config.get("PLUGIN_LIKE_URL_PREFIX", "/like")
    )


SETTINGS = SettingGroup(
    key="like",
    name="Like Settings",
    description="Settings for the like plugin.",
    settings=(
        BoolSetting(
            key="ALLOW_SELF_LIKE",
            value=DEFAULT_ALLOW_SELF_LIKE,
            name="Allow liking your own posts",
            description="If enabled, a user may like their own posts.",
        ),
    ),
)


@hookimpl
def flaskbb_load_setting_groups():
    return SETTINGS


@hookimpl
def flaskbb_tpl_post_menu_before(post: Post):
    user = real(current_user)
    can_like = user.is_authenticated and can_like_post(user, post)
    already_liked = user.is_authenticated and has_liked(user, post)
    return render_template(
        "like/_like_button.html",
        post=post,
        can_like=can_like,
        already_liked=already_liked,
        form=LikeActionForm(),
    )


@hookimpl
def flaskbb_tpl_post_author_info_after(user: User | None, post: Post):
    if user is None:
        return None

    return render_template(
        "like/_like_counts.html",
        user=user,
        likes_given=likes_given_count(user),
        likes_received=likes_received_count(user),
    )


@hookimpl
def flaskbb_tpl_scripts():
    return render_template("like/_scripts.html")


@hookimpl
def flaskbb_tpl_profile_sidebar_links(user: User):
    return NavigationLink(
        endpoint="like.liked_posts",
        name=_("Liked posts"),
        icon="fa fa-heart",
        urlforkwargs={"username": user.username},
    )
