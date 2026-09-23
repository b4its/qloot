"""certificate on-chain anchoring

Adds anchor_status / anchor_tx_hash / anchored_at to certificates so a
credential's verification hash can be anchored on the QTC contract.

Revision ID: a4b5c6d7e8f9
Revises: f3a1b2c4d5e6
Create Date: 2026-09-24 00:00:10.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4b5c6d7e8f9"
down_revision: str | None = "f3a1b2c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "certificates",
        sa.Column("anchor_status", sa.String(length=16), nullable=False, server_default="unanchored"),
    )
    op.add_column(
        "certificates", sa.Column("anchor_tx_hash", sa.String(length=66), nullable=True)
    )
    op.add_column(
        "certificates",
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("certificates", "anchored_at")
    op.drop_column("certificates", "anchor_tx_hash")
    op.drop_column("certificates", "anchor_status")
