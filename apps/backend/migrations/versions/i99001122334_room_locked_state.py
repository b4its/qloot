"""room locked state

Adds rooms.is_locked (host control that freezes new joins while status
stays "open" — GAME-08). The dead room-chat WS branch was removed in the
same commit as this migration (no schema change needed for that).

Revision ID: i99001122334
Revises: h88990011223
Create Date: 2026-09-24 00:07:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "i99001122334"
down_revision: str | None = "h88990011223"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rooms",
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("rooms", "is_locked")
