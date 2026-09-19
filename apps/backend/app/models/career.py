"""Career guidance models: academic grades, personality, recommendations,
roadmap milestones, consultations and the resource library.

This mirrors the EduPath feature set, adapted to QLoot and run as a fully
simulated (deterministic) module.
"""

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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, utcnow


class AcademicGrade(Base, TimestampMixin):
    """A per-subject grade (0-100) for a student in a term."""

    __tablename__ = "academic_grades"
    __table_args__ = (
        UniqueConstraint("user_id", "subject", "term", name="uq_grade_user_subject_term"),
        Index("ix_grades_user_term", "user_id", "term"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    term: Mapped[str] = mapped_column(String(32), default="2025/2026-genap", nullable=False)


class PersonalityResult(Base):
    """Result of a Big Five (BFI-2 style) personality simulation."""

    __tablename__ = "personality_results"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    openness: Mapped[int] = mapped_column(Integer, nullable=False)
    conscientiousness: Mapped[int] = mapped_column(Integer, nullable=False)
    extraversion: Mapped[int] = mapped_column(Integer, nullable=False)
    agreeableness: Mapped[int] = mapped_column(Integer, nullable=False)
    neuroticism: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    answers: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class CareerRecommendation(Base):
    """AI recommendation for a major, with a human-in-the-loop status."""

    __tablename__ = "career_recommendations"
    __table_args__ = (Index("ix_career_rec_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    major: Mapped[str] = mapped_column(String(128), nullable=False)
    fit_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    academic_fit: Mapped[int] = mapped_column(Integer, nullable=False)
    personality_fit: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    universities: Mapped[list | None] = mapped_column(JSONB)
    admission_paths: Mapped[list | None] = mapped_column(JSONB)
    skills: Mapped[list | None] = mapped_column(JSONB)
    careers: Mapped[list | None] = mapped_column(JSONB)
    rank: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class RoadmapMilestone(Base):
    __tablename__ = "roadmap_milestones"
    __table_args__ = (UniqueConstraint("user_id", "position", name="uq_milestone_user_position"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="not_started", nullable=False)
    tasks: Mapped[list | None] = mapped_column(JSONB)


class Consultation(Base):
    """BK (counselling) session booking."""

    __tablename__ = "consultations"
    __table_args__ = (Index("ix_consultations_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    counselor: Mapped[str] = mapped_column(String(128), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ResourceItem(Base):
    """Static-ish resource library entry (courses, clubs, materials)."""

    __tablename__ = "resource_items"
    __table_args__ = (UniqueConstraint("code", name="uq_resource_items_code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # course|extracurricular|material
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(128))
    is_free: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tags: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
