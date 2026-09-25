"""drop unused community hidden_reason column

The C73 moderation work added community_posts.hidden_reason but nothing ever
read it (the reason is preserved on the report and the moderation audit row).
Per the plan's "delete dead surface" rule, remove the column.

Revision ID: q77889900112
Revises: p66778899001
Create Date: 2026-09-24 07:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "q77889900112"
down_revision: str | None = "p66778899001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("community_posts", "hidden_reason")


def downgrade() -> None:
    op.add_column(
        "community_posts",
        sa.Column("hidden_reason", sa.String(length=255), nullable=True),
    )
