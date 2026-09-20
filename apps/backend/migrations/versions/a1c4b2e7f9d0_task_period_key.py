"""task completion period key (daily resets)

Revision ID: a1c4b2e7f9d0
Revises: 78b66b207e43
Create Date: 2026-09-21 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4b2e7f9d0"
down_revision: str | None = "78b66b207e43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add the period bucket so recurring (daily) tasks can be completed once
    # per period, then swap the unique constraint to include it. The
    # server_default only backfills existing rows; it is dropped afterwards so
    # the column matches the ORM model (Python-side default only).
    op.add_column(
        "task_completions",
        sa.Column("period_key", sa.String(length=32), nullable=False, server_default=""),
    )
    op.alter_column("task_completions", "period_key", server_default=None)
    op.drop_constraint("uq_task_completions_task_user", "task_completions", type_="unique")
    op.create_unique_constraint(
        "uq_task_completions_task_user_period",
        "task_completions",
        ["task_id", "user_id", "period_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_task_completions_task_user_period", "task_completions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_task_completions_task_user", "task_completions", ["task_id", "user_id"]
    )
    op.drop_column("task_completions", "period_key")
