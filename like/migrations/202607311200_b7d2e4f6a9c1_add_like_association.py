"""Add like_association and the user like counters

Revision ID: b7d2e4f6a9c1
Revises:
Create Date: 2026-07-31 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7d2e4f6a9c1"
down_revision = None
branch_labels = ("like",)
depends_on = "8ad96e49dc6"  # flaskbb core init migration - creates posts/users


def upgrade():
    con = op.get_bind()
    inspector = sa.inspect(con.engine)

    if not inspector.has_table("like_association"):
        op.create_table(
            "like_association",
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["post_id"],
                ["posts.id"],
                name=op.f("fk_like_association_post_id_posts"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name=op.f("fk_like_association_user_id_users"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint(
                "post_id", "user_id", name=op.f("pk_like_association")
            ),
        )

    # a fresh install that went through db.create_all() already has them
    user_columns = {c["name"] for c in inspector.get_columns("users")}
    with op.batch_alter_table("users", schema=None) as batch_op:
        if "likes_given" not in user_columns:
            batch_op.add_column(
                sa.Column(
                    "likes_given", sa.Integer(), nullable=False, server_default="0"
                )
            )
        if "likes_received" not in user_columns:
            batch_op.add_column(
                sa.Column(
                    "likes_received", sa.Integer(), nullable=False, server_default="0"
                )
            )

    op.execute(
        """
        UPDATE users SET likes_given = (
            SELECT COUNT(*) FROM like_association
            WHERE like_association.user_id = users.id
        )
        """
    )
    op.execute(
        """
        UPDATE users SET likes_received = (
            SELECT COUNT(*) FROM like_association
            JOIN posts ON posts.id = like_association.post_id
            WHERE posts.user_id = users.id
        )
        """
    )


def downgrade():
    op.drop_table("like_association")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("likes_received")
        batch_op.drop_column("likes_given")
