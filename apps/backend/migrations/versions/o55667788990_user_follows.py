"""user follow graph

COMM-06: adds a user_follows table so users can follow each other and filter
the community feed to who they follow.

Revision ID: o55667788990
Revises: n44556677889
Create Date: 2026-09-24 05:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "o55667788990"
down_revision: str | None = "n44556677889"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_follows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("followee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["followee_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("follower_id", "followee_id", name="uq_user_follows_pair"),
    )
    op.create_index("ix_user_follows_followee", "user_follows", ["followee_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_follows_followee", table_name="user_follows")
    op.drop_table("user_follows")
