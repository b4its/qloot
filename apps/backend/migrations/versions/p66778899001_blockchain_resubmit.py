"""blockchain transaction resubmit counter

WEB3-06b: a stuck transaction is resubmitted with a fee bump up to a maximum
number of attempts before being marked dropped and compensated. This tracks
the resubmit count.

Revision ID: p66778899001
Revises: o55667788990
Create Date: 2026-09-24 06:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p66778899001"
down_revision: str | None = "o55667788990"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "blockchain_transactions",
        sa.Column("resubmit_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("blockchain_transactions", "resubmit_count")
