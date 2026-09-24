"""attempt proctoring events

Adds attempt_events for proctoring telemetry (tab blur / focus loss / dwell).

Revision ID: b22334455667
Revises: a11223344556
Create Date: 2026-09-24 00:01:20.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b22334455667"
down_revision: str | None = "a11223344556"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attempt_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["exam_attempts.id"],
            name=op.f("fk_attempt_events_attempt_id_exam_attempts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attempt_events")),
    )
    op.create_index("ix_attempt_events_attempt", "attempt_events", ["attempt_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_attempt_events_attempt", table_name="attempt_events")
    op.drop_table("attempt_events")
