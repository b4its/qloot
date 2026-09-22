"""wallet asset balances and drop vestigial on-chain ids

Adds the per-user secondary-asset balance table (QTC/ORT) used by the
OPT -> QTC/ORT swap flow, and removes the now-vestigial ``on_chain_id`` columns
from ``badges`` and ``courses`` (badges and courses are off-chain; the on-chain
contracts hold only the fungible assets OPT/QTC/ORT).

Revision ID: b3c9f1a2d4e5
Revises: adc4a40c4dd5
Create Date: 2026-09-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c9f1a2d4e5"
down_revision: str | None = "adc4a40c4dd5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wallet_asset_balances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("asset", sa.String(length=8), nullable=False),
        sa.Column("cached_balance", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_wallet_asset_balances_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallet_asset_balances")),
        sa.UniqueConstraint("user_id", "asset", name="uq_wallet_asset_user_asset"),
    )
    op.create_index(
        op.f("ix_wallet_asset_balances_user_id"),
        "wallet_asset_balances",
        ["user_id"],
        unique=False,
    )
    # Vestigial on-chain ids (badges/courses are off-chain only).
    op.drop_constraint(op.f("uq_courses_on_chain_id"), "courses", type_="unique")
    op.drop_column("courses", "on_chain_id")
    op.drop_constraint(op.f("uq_badges_on_chain_id"), "badges", type_="unique")
    op.drop_column("badges", "on_chain_id")


def downgrade() -> None:
    op.add_column("badges", sa.Column("on_chain_id", sa.Integer(), nullable=True))
    op.create_unique_constraint(op.f("uq_badges_on_chain_id"), "badges", ["on_chain_id"])
    op.add_column("courses", sa.Column("on_chain_id", sa.Integer(), nullable=True))
    op.create_unique_constraint(op.f("uq_courses_on_chain_id"), "courses", ["on_chain_id"])
    op.drop_index(op.f("ix_wallet_asset_balances_user_id"), table_name="wallet_asset_balances")
    op.drop_table("wallet_asset_balances")
