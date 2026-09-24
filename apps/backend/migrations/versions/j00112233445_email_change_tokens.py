"""email change tokens

Adds email_change_tokens, mirroring password_reset_tokens' shape, for the
verified change-email flow (AUTH-04). The pending new_email lives on the
token, not on the user, until confirmed.

Revision ID: j00112233445
Revises: i99001122334
Create Date: 2026-09-24 00:08:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j00112233445"
down_revision: str | None = "i99001122334"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_change_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("new_email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_email_change_tokens_user_id", "email_change_tokens", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_email_change_tokens_user_id", table_name="email_change_tokens")
    op.drop_table("email_change_tokens")
