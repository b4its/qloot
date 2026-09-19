"""Ranking models: leaderboards, entries, snapshots."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow


class Leaderboard(Base, TimestampMixin):
    __tablename__ = "leaderboards"
    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "period", name="uq_leaderboards_scope_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scope: Mapped[str] = mapped_column(
        String(16), default="global", nullable=False
    )  # global|room|quest
    scope_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    period: Mapped[str] = mapped_column(String(16), default="all", nullable=False)
    is_materialized: Mapped[bool] = mapped_column(default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=func.now(), nullable=False
    )

    entries: Mapped[list[LeaderboardEntry]] = relationship(
        back_populates="leaderboard", cascade="all, delete-orphan"
    )


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"
    __table_args__ = (
        UniqueConstraint("leaderboard_id", "user_id", name="uq_leaderboard_entries_lb_user"),
        Index("ix_leaderboard_entries_lb_rank", "leaderboard_id", "rank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    leaderboard_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("leaderboards.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score_bp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opc_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    badge: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=func.now(), nullable=False
    )

    leaderboard: Mapped[Leaderboard] = relationship(back_populates="entries")


class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
