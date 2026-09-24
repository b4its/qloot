"""material extraction status

Adds learning_materials.extraction_status to signal extraction quality
(ok / empty / ocr) at upload time.

Revision ID: e55667788990
Revises: d44556677889
Create Date: 2026-09-24 00:03:10.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e55667788990"
down_revision: str | None = "d44556677889"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_materials",
        sa.Column("extraction_status", sa.String(length=16), nullable=False, server_default="ok"),
    )
    # Backfill: existing materials with little text are marked empty.
    op.execute(
        "UPDATE learning_materials SET extraction_status = 'empty' "
        "WHERE coalesce(length(extracted_text), 0) < 20"
    )


def downgrade() -> None:
    op.drop_column("learning_materials", "extraction_status")
