"""consultation workflow and message thread

CARE-06: consultations gain a real counselor user (counselor_user_id) and a
completed_at timestamp, plus a consultation_messages table so the student and
counselor can exchange messages. Existing rows keep counselor_user_id NULL
(they fall back to the display name).

Revision ID: l22334455667
Revises: k11223344556
Create Date: 2026-09-24 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "l22334455667"
down_revision: str | None = "k11223344556"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "consultations",
        sa.Column("counselor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "consultations",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_consultations_counselor_user_id_users",
        "consultations",
        "users",
        ["counselor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "consultation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["consultations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_consultation_msg_consult_created",
        "consultation_messages",
        ["consultation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_consultation_msg_consult_created", table_name="consultation_messages")
    op.drop_table("consultation_messages")
    op.drop_constraint(
        "fk_consultations_counselor_user_id_users", "consultations", type_="foreignkey"
    )
    op.drop_column("consultations", "completed_at")
    op.drop_column("consultations", "counselor_user_id")
