"""material chunks (RAG index)

Adds material_chunks: overlapping text chunks of a material plus their
embedding vectors, used for RAG retrieval in summary/Q&A.

Revision ID: d44556677889
Revises: c33445566778
Create Date: 2026-09-24 00:03:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d44556677889"
down_revision: str | None = "c33445566778"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("material_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["learning_materials.id"],
            name=op.f("fk_material_chunks_material_id_learning_materials"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_material_chunks")),
    )
    op.create_index(
        "ix_material_chunks_material", "material_chunks", ["material_id", "position"]
    )


def downgrade() -> None:
    op.drop_index("ix_material_chunks_material", table_name="material_chunks")
    op.drop_table("material_chunks")
