"""badge rarity tiers

Adds badges.rarity (common/rare/epic/legendary), backfilled from each
badge's existing points so pre-existing catalog rows get a sensible tier
without a data migration script.

Revision ID: g77889900112
Revises: f66778899001
Create Date: 2026-09-24 00:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g77889900112"
down_revision: str | None = "f66778899001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "badges",
        sa.Column("rarity", sa.String(length=16), nullable=False, server_default="common"),
    )
    op.execute("UPDATE badges SET rarity = 'rare' WHERE points >= 20 AND points < 40")
    op.execute("UPDATE badges SET rarity = 'epic' WHERE points >= 40 AND points < 100")
    op.execute("UPDATE badges SET rarity = 'legendary' WHERE points >= 100")


def downgrade() -> None:
    op.drop_column("badges", "rarity")
