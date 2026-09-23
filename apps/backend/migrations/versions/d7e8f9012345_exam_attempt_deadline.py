"""exam attempt server-side deadline

Adds exam_attempts.expires_at (indexed) so the timer is enforced server-side
and a sweeper can auto-submit abandoned attempts. Backfills in-progress rows
from started_at + the exam duration.

Revision ID: d7e8f9012345
Revises: c6d7e8f90123
Create Date: 2026-09-24 00:00:40.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7e8f9012345"
down_revision: str | None = "c6d7e8f90123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exam_attempts", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_exam_attempts_expires_at", "exam_attempts", ["expires_at"])
    # Backfill existing in-progress attempts from started_at + duration, capped
    # at the exam's closes_at when set.
    op.execute(
        """
        UPDATE exam_attempts a
        SET expires_at = LEAST(
            a.started_at + (e.duration_minutes::text || ' minutes')::interval,
            COALESCE(
                e.closes_at,
                a.started_at + (e.duration_minutes::text || ' minutes')::interval
            )
        )
        FROM exams e
        WHERE e.id = a.exam_id
          AND a.expires_at IS NULL
          AND a.status = 'in_progress'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_exam_attempts_expires_at", table_name="exam_attempts")
    op.drop_column("exam_attempts", "expires_at")
