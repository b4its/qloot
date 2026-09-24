"""community comment replies and editing

COMM-02: comments gain a parent_id (nested replies) and edited_at marker.

Revision ID: n44556677889
Revises: m33445566778
Create Date: 2026-09-24 04:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n44556677889"
down_revision: str | None = "m33445566778"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "community_comments",
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "community_comments",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_community_comments_parent_id_self",
        "community_comments",
        "community_comments",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_community_comments_parent_id_self", "community_comments", type_="foreignkey"
    )
    op.drop_column("community_comments", "edited_at")
    op.drop_column("community_comments", "parent_id")
