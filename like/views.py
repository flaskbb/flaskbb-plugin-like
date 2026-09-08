"""
like.views
~~~~~~~~~~

The views for liking/unliking a post and for a user's liked-posts page.

:copyright: (c) 2026 by Peter Justin, (c) 2018 by Михаил Лебедев.
:license: BSD License, see LICENSE for more details.
"""

from flask import Blueprint, abort, flash, jsonify, redirect, request
from flask.views import MethodView
from flask_babelplus import gettext as _
from flask_login import current_user, login_required
from flaskbb.settings import flaskbb_config
from flaskbb.extensions import db
from flaskbb.forum.models import Forum, Post, Topic
from flaskbb.user.models import Group, User
from flaskbb.utils.helpers import real, register_view, render_template

from .forms import LikeActionForm
from .models import PostLike
from .utils import (
    can_like_post,
    has_liked,
    like_post,
    likes_given_count,
    likes_received_count,
    unlike_post,
)

like_bp = Blueprint(
    "like", __name__, template_folder="templates", static_folder="static"
)


def _is_ajax() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _counts_for(user: User) -> dict[str, int]:
    return {
        "user_id": user.id,
        "given": likes_given_count(user),
        "received": likes_received_count(user),
    }


def _like_state(post: Post, user: User):
    """The re-rendered like widget plus the counters the (un)like changed.

    Both counters are read after ``like_post``/``unlike_post`` committed, so
    the values the after_insert/after_delete events wrote are already visible.
    They are sent as numbers rather than markup because they live in the post
    author sidebar - a different part of the page from the widget, and
    possibly in several places at once if the same user has more than one post
    on it.
    """
    counts = [_counts_for(user)]
    if post.user is not None and post.user != user:
        counts.append(_counts_for(post.user))
    return jsonify(
        widget=render_template(
            "like/_like_button.html",
            post=post,
            can_like=can_like_post(user, post),
            already_liked=has_liked(user, post),
            form=LikeActionForm(),
        ),
        counts=counts,
    )


class LikePost(MethodView):
    decorators = [login_required]

    def post(self, post_id: int):
        post = Post.get_or_404(Post.id == post_id)
        user = real(current_user)

        form = LikeActionForm()
        if not form.validate_on_submit():
            flash(_("Could not verify the like request, please try again."), "danger")
            return redirect(post.url)

        if has_liked(user, post) or not can_like_post(user, post):
            abort(403)

        like_post(user, post)
        if _is_ajax():
            return _like_state(post, user)
        return redirect(post.url)


class UnlikePost(MethodView):
    decorators = [login_required]

    def post(self, post_id: int):
        post = Post.get_or_404(Post.id == post_id)
        user = real(current_user)

        form = LikeActionForm()
        if not form.validate_on_submit():
            flash(_("Could not verify the like request, please try again."), "danger")
            return redirect(post.url)

        if not has_liked(user, post):
            abort(403)

        unlike_post(user, post)
        if _is_ajax():
            return _like_state(post, user)
        return redirect(post.url)


class LikedPosts(MethodView):
    def get(self, username: str):
        page = request.args.get("page", 1, type=int)
        user = User.get_by_or_404(username=username)
        viewer = real(current_user)
        group_ids = [g.id for g in viewer.groups]

        stmt = (
            db.select(Post)
            .join(PostLike, PostLike.post_id == Post.id)
            .join(Topic, Post.topic_id == Topic.id)
            .join(Forum, Topic.forum_id == Forum.id)
            .where(
                PostLike.user_id == user.id,
                Forum.groups.any(Group.id.in_(group_ids)),
            )
            .order_by(Post.id.desc())
        )
        posts = db.paginate(stmt, page=page, per_page=flaskbb_config["POSTS_PER_PAGE"])
        return render_template("like/liked_posts.html", user=user, posts=posts)


register_view(
    like_bp, routes=["/<int:post_id>/like"], view_func=LikePost.as_view("like_post")
)
register_view(
    like_bp,
    routes=["/<int:post_id>/unlike"],
    view_func=UnlikePost.as_view("unlike_post"),
)
register_view(
    like_bp,
    routes=["/<username>/liked-posts"],
    view_func=LikedPosts.as_view("liked_posts"),
)
