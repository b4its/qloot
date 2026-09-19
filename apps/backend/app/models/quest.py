"""Quest / task models and deterministic winner selection."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow


class Quest(Base, TimestampMixin):
    __tablename__ = "quests"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("rooms.id", ondelete="SET NULL")
    )
    exam_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exams.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), default="exam", nullable=False)
    top_n_winners: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    reward_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rules: Mapped[list[QuestRule]] = relationship(
        back_populates="quest", cascade="all, delete-orphan"
    )
    winners: Mapped[list[QuestWinner]] = relationship(
        back_populates="quest", cascade="all, delete-orphan"
    )


class QuestRule(Base):
    __tablename__ = "quest_rules"
    __table_args__ = (UniqueConstraint("quest_id", "rank", name="uq_quest_rules_quest_rank"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quest_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    min_score_bp: Mapped[int | None] = mapped_column(Integer)

    quest: Mapped[Quest] = relationship(back_populates="rules")


class QuestAttempt(Base, TimestampMixin):
    __tablename__ = "quest_attempts"
    __table_args__ = (UniqueConstraint("quest_id", "user_id", name="uq_quest_attempts_quest_user"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quest_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("quests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exam_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exam_attempts.id", ondelete="SET NULL")
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    score_bp: Mapped[int | None] = mapped_column(Integer)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    invalid_reason: Mapped[str | None] = mapped_column(String(255))


class QuestWinner(Base):
    """Deterministic winners. Unique on (quest, rank) and (quest, user)."""

    __tablename__ = "quest_winners"
    __table_args__ = (
        UniqueConstraint("quest_id", "rank", name="uq_quest_winners_quest_rank"),
        UniqueConstraint("quest_id", "user_id", name="uq_quest_winners_quest_user"),
        Index("ix_quest_winners_quest_rank", "quest_id", "rank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quest_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    attempt_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reward_key: Mapped[str] = mapped_column(String(66), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    quest: Mapped[Quest] = relationship(back_populates="winners")


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(32), default="daily", nullable=False)
    reward_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL")
    )
    quest_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("quests.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict | None] = mapped_column(JSONB)


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_completions_task_user"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reward_key: Mapped[str] = mapped_column(String(66), unique=True, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
