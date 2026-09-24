"""community reporting and moderation

COMM-01: adds a hidden flag (+reason) to community posts and comments and a
community_reports table so users can report content and admins can moderate.

Revision ID: m33445566778
Revises: l22334455667
Create Date: 2026-09-24 03:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m33445566778"
down_revision: str | None = "l22334455667"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "community_posts",
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "community_posts", sa.Column("hidden_reason", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "community_comments",
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "community_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reporter_id", "target_type", "target_id", name="uq_community_report_target"
        ),
    )
    op.create_index(
        "ix_community_reports_status_created",
        "community_reports",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_community_reports_status_created", table_name="community_reports")
    op.drop_table("community_reports")
    op.drop_column("community_comments", "hidden")
    op.drop_column("community_posts", "hidden_reason")
    op.drop_column("community_posts", "hidden")
