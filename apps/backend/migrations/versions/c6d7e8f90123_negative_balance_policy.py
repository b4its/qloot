"""negative-balance policy: is_in_debt flag + asset non-negative CHECK

Adds an explicit policy for negative OPT balances: a compensation-driven
negative balance flags the account (``is_in_debt``) instead of being silent.
Also adds a DB CHECK forbidding negative secondary-asset (QTC/ORT) balances.

Revision ID: c6d7e8f90123
Revises: b5c6d7e8f901
Create Date: 2026-09-24 00:00:30.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6d7e8f90123"
down_revision: str | None = "b5c6d7e8f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "wallet_accounts",
        sa.Column("is_in_debt", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Backfill: any account already negative is flagged.
    op.execute("UPDATE wallet_accounts SET is_in_debt = TRUE WHERE cached_balance < 0")
    op.create_check_constraint(
        "ck_wallet_asset_balance_non_negative",
        "wallet_asset_balances",
        "cached_balance >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_wallet_asset_balance_non_negative", "wallet_asset_balances", type_="check"
    )
    op.drop_column("wallet_accounts", "is_in_debt")
