"""question structured answer keys

Adds questions.answer_json for the non-single-label question types
(multi_select correct set, numeric value/tolerance, fill_blank accepted
strings, matching pairs, ordering sequence).

Revision ID: c33445566778
Revises: b22334455667
Create Date: 2026-09-24 00:02:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c33445566778"
down_revision: str | None = "b22334455667"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("answer_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("questions", "answer_json")
