"""withdrawal approval: reviewer, fee, reject reason

Adds fee_amount / reviewed_by / reviewed_at / reject_reason to
withdrawal_requests for the approval state machine.

Revision ID: b5c6d7e8f901
Revises: a4b5c6d7e8f9
Create Date: 2026-09-24 00:00:20.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5c6d7e8f901"
down_revision: str | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "withdrawal_requests",
        sa.Column("fee_amount", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "withdrawal_requests", sa.Column("reviewed_by", sa.UUID(), nullable=True)
    )
    op.add_column(
        "withdrawal_requests",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "withdrawal_requests", sa.Column("reject_reason", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("withdrawal_requests", "reject_reason")
    op.drop_column("withdrawal_requests", "reviewed_at")
    op.drop_column("withdrawal_requests", "reviewed_by")
    op.drop_column("withdrawal_requests", "fee_amount")
