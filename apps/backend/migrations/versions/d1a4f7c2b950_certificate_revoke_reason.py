"""certificate revoke reason

Revision ID: d1a4f7c2b950
Revises: c7e2a9f1b430
Create Date: 2026-09-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1a4f7c2b950"
down_revision: str | None = "c7e2a9f1b430"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("certificates", sa.Column("revoked_reason", sa.String(length=255)))


def downgrade() -> None:
    op.drop_column("certificates", "revoked_reason")
