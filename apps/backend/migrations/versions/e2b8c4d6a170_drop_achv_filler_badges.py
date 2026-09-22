"""drop unreachable achv- filler badges

Revision ID: e2b8c4d6a170
Revises: d1a4f7c2b950
Create Date: 2026-09-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e2b8c4d6a170"
down_revision: str | None = "d1a4f7c2b950"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove the seed-only ``achv-***`` badges: no application code can award
    # them, so they flooded the badge page with permanently-locked cards. Only
    # delete rows nobody owns (safe even if a demo user somehow has one).
    op.execute(
        """
        DELETE FROM badges
        WHERE code LIKE 'achv-%'
          AND id NOT IN (SELECT badge_id FROM user_badges)
        """
    )


def downgrade() -> None:
    # Not restorable (the filler is intentionally removed); no-op.
    pass
