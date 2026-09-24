"""exam late-submission grace and penalty

Adds exams.grace_seconds and exams.late_penalty_bp so a submit inside the
grace window is accepted and scored with a penalty.

Revision ID: a11223344556
Revises: f90123456789
Create Date: 2026-09-24 00:01:10.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a11223344556"
down_revision: str | None = "f90123456789"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column("grace_seconds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "exams",
        sa.Column("late_penalty_bp", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("exams", "late_penalty_bp")
    op.drop_column("exams", "grace_seconds")
