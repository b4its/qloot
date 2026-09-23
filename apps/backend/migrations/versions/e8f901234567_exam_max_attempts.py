"""exam max attempts

Adds exams.max_attempts (0 = unlimited); default 1 preserves single-attempt
behaviour for existing/seed exams.

Revision ID: e8f901234567
Revises: d7e8f9012345
Create Date: 2026-09-24 00:00:50.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8f901234567"
down_revision: str | None = "d7e8f9012345"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("exams", "max_attempts")
