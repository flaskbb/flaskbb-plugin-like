"""
like.utils
~~~~~~~~~~

Helpers for liking/unliking a post and for counting a user's likes.

:copyright: (c) 2026 by Peter Justin, (c) 2018 by Михаил Лебедев.
:license: BSD License, see LICENSE for more details.
"""

from collections.abc import Sequence
from typing import cast

from flaskbb.extensions import db
from flaskbb.forum.models import Post
from flaskbb.permissions import permission_manager
from flaskbb.settings import flaskbb_config
from flaskbb.user.models import User
from sqlalchemy import func

from .models import LikePost, LikeUser, PostLike

DEFAULT_ALLOW_SELF_LIKE = False


def allow_self_like() -> bool:
    # Falls back to the setting's own default when the plugin hasn't been
    # installed yet (admin panel > Plugins > Install seeds it into the
    # settings table).
    value = flaskbb_config["LIKE_ALLOW_SELF_LIKE"]
    return bool(value) if value is not None else DEFAULT_ALLOW_SELF_LIKE


def can_like_post(user: User, post: Post) -> bool:
    """Mirrors the old vanity plugin's ``Post.allowed_to_like`` - a post
    can be liked if its topic and forum aren't locked, the post still has
    a topic (it might have been orphaned by a delete), and the user shares
    a group with the post's forum. Liking your own post is only allowed
    when the ``LIKE_ALLOW_SELF_LIKE`` setting is on.
    """
    topic = post.topic
    if topic is None or topic.locked or topic.forum.locked:
        return False
    if not allow_self_like() and post.user == user:
        return False
    return permission_manager.for_user(user).can_access(topic.forum)


def like_post(user: User, post: Post) -> None:
    PostLike(post_id=post.id, user_id=user.id).save()


def _find_like(user: User, post: Post) -> PostLike | None:
    # liked_by_users is batch-loaded for every Post a page loads (see
    # models.py), so this never costs a query of its own
    likes = cast(LikePost, post).liked_by_users
    return next((like for like in likes if like.user_id == user.id), None)


def unlike_post(user: User, post: Post) -> None:
    like = _find_like(user, post)
    if like is not None:
        like.delete()


def has_liked(user: User, post: Post) -> bool:
    return _find_like(user, post) is not None


def post_likers(post: Post) -> Sequence[User]:
    return (
        db.session.execute(
            db.select(User)
            .join(PostLike, PostLike.user_id == User.id)
            .where(PostLike.post_id == post.id)
            .order_by(User.username)
        )
        .scalars()
        .all()
    )


def likes_given_count(user: User) -> int:
    return cast(LikeUser, user).likes_given


def likes_received_count(user: User) -> int:
    return cast(LikeUser, user).likes_received


def recalculate_like_counts(user: User) -> User:
    """Recomputes both counters from like_association. The counters are
    maintained by the events in like/models.py, which cover every ORM path;
    anything that deletes likes with raw SQL (or a stale DB from before the
    counters existed) needs this to resync.
    """
    # PostLike has no `id` - its primary key is (post_id, user_id) - so
    # CRUDMixin.count()'s default `column=cls.id` doesn't exist here.
    counts = cast(LikeUser, user)
    counts.likes_given = PostLike.count(PostLike.user_id == user.id, column=PostLike.post_id)
    counts.likes_received = db.session.execute(
        db.select(func.count(PostLike.post_id))
        .join(Post, PostLike.post_id == Post.id)
        .where(Post.user_id == user.id)
    ).scalar_one()
    user.save()
    return user
