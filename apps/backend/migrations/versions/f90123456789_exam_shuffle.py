"""exam per-attempt shuffle flags

Adds exams.shuffle_questions / shuffle_options for per-attempt deterministic
question and option ordering (anti-cheat).

Revision ID: f90123456789
Revises: e8f901234567
Create Date: 2026-09-24 00:01:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f90123456789"
down_revision: str | None = "e8f901234567"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column("shuffle_questions", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "exams",
        sa.Column("shuffle_options", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("exams", "shuffle_options")
    op.drop_column("exams", "shuffle_questions")
