"""ai usage charges (ORT metering)

Adds ``ai_usage_charges``: one row per AI job that consumed ORT (or a free-tier
slot). Makes AI metering idempotent and auditable and backs the "free AI
requests remaining" query.

Revision ID: f3a1b2c4d5e6
Revises: e2b8c4d6a170
Create Date: 2026-09-24 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a1b2c4d5e6"
down_revision: str | None = "e2b8c4d6a170"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_charges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("charged", sa.Boolean(), nullable=False),
        sa.Column("refunded", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_usage_charges_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage_charges")),
        sa.UniqueConstraint("job_id", name="uq_ai_usage_job"),
    )
    op.create_index(
        "ix_ai_usage_user_created",
        "ai_usage_charges",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_user_created", table_name="ai_usage_charges")
    op.drop_table("ai_usage_charges")
