"""unique grading result per job

Revision ID: c7e2a9f1b430
Revises: b3c9f1a2d4e5
Create Date: 2026-09-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c7e2a9f1b430"
down_revision: str | None = "b3c9f1a2d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # One grading result per job: makes a reaper requeue (slow-but-alive worker)
    # safe — a second result insert can no longer create a duplicate row.
    # Dedupe any pre-existing rows first so the constraint can be added.
    op.execute(
        """
        DELETE FROM grading_results a
        USING grading_results b
        WHERE a.job_id = b.job_id AND a.id > b.id
        """
    )
    op.create_unique_constraint("uq_grading_results_job", "grading_results", ["job_id"])


def downgrade() -> None:
    op.drop_constraint("uq_grading_results_job", "grading_results", type_="unique")
