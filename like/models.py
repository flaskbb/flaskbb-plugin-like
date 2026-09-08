"""
like.models
~~~~~~~~~~~

The model for a user's like on a post.

:copyright: (c) 2026 by Peter Justin, (c) 2018 by Михаил Лебедев.
:license: BSD License, see LICENSE for more details.
"""

from typing import TYPE_CHECKING, cast

from flaskbb.extensions import db
from flaskbb.forum.models import Post
from flaskbb.user.models import User
from flaskbb.utils.database import BaseModel
from sqlalchemy import Connection, ForeignKey, Integer, Table, event, update
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship


class PostLike(BaseModel):
    __tablename__ = "like_association"

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # Both sides load via `selectin`, never `joined` - see
    # https://github.com/flaskbb/flaskbb/issues/503. `joined` folds into
    # whatever query loads a Post/User, including flaskbb's own hand-built
    # outerjoin in Topic.get_posts, and corrupts its column layout.
    # `selectin` always runs as its own separate, batched query instead, so
    # it can chain (post -> liked_by_users -> user) without ever touching a
    # query this plugin doesn't own.
    post: Mapped["Post"] = relationship(
        "Post",
        backref=db.backref(
            "liked_by_users", lazy="selectin", cascade="all, delete-orphan"
        ),
    )
    user: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
        backref=db.backref("user_liked_posts", cascade="all, delete-orphan"),
    )


Post.likers = association_proxy(
    "liked_by_users",
    "user",
    creator=lambda user: PostLike(user=user),  # pyright: ignore
)

# Denormalized like counters on the core `users` table. Counting from
# like_association on every render costs a query per distinct post author
# per page; these are two columns that come along with the User row that
# flaskbb has already loaded.
#
# Assigning a mapped_column onto an already-mapped class goes through
# declarative's _add_attribute, which appends the column to the `users`
# Table and adds the property to User's mapper - the same monkey-patching
# this plugin already does with Post.likers above. like/migrations adds
# the actual DB columns.
User.likes_given = mapped_column(Integer, default=0, server_default="0", nullable=False)
User.likes_received = mapped_column(
    Integer, default=0, server_default="0", nullable=False
)


if TYPE_CHECKING:

    class LikeUser(User):
        """A ``User`` with the two counters added above. They are added at
        import time, so a type checker cannot see them on ``User`` itself -
        cast to this to read or write them.
        """

        likes_given: int = 0
        likes_received: int = 0

else:
    LikeUser = User


def _apply_delta(connection: Connection, like: PostLike, delta: int) -> None:
    """Two people liking the same post at once can't lose an increment. Runs
    on the flush's connection, in the same transaction as the row itself.

    The post's author is looked up as a subquery instead of via
    ``like.post.user_id``: emitting a lazy load from inside a flush event is
    not allowed, and on the delete path the Post may already be gone from the
    session. If the post has no author (guest post, or the author's row went
    first), the subquery is NULL and the UPDATE matches nothing.
    """
    users = cast(Table, User.__table__)
    posts = cast(Table, Post.__table__)
    author_id = (
        db.select(posts.c.user_id).where(posts.c.id == like.post_id).scalar_subquery()
    )
    connection.execute(
        update(users)
        .where(users.c.id == like.user_id)
        .values(likes_given=users.c.likes_given + delta)
    )
    connection.execute(
        update(users)
        .where(users.c.id == author_id)
        .values(likes_received=users.c.likes_received + delta)
    )


@event.listens_for(PostLike, "after_insert")
def _increment_like_counts(
    mapper: Mapper[PostLike], connection: Connection, target: PostLike
) -> None:
    _apply_delta(connection, target, 1)


@event.listens_for(PostLike, "after_delete")
def _decrement_like_counts(
    mapper: Mapper[PostLike], connection: Connection, target: PostLike
) -> None:
    # Keeps the counters honest on paths this plugin never sees: deleting a
    # post or a user cascades through the ORM relationships above, which
    # deletes each PostLike individually and fires this. A raw SQL delete
    # against like_association bypasses it - see recalculate_like_counts.
    _apply_delta(connection, target, -1)
