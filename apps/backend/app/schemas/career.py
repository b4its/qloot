"""Career guidance schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class GradeIn(BaseModel):
    subject: str = Field(min_length=1, max_length=64)
    grade: int = Field(ge=0, le=100)
    term: str = Field(default="2025/2026-genap", max_length=32)


class GradeOut(ORMModel):
    subject: str
    grade: int
    term: str


class Insight(BaseModel):
    kind: str
    title: str
    detail: str


class DashboardOut(BaseModel):
    average: int
    strong_subject: str | None
    weak_subject: str | None
    subjects: list[dict]
    trend: list[dict]
    radar: list[dict]
    insights: list[Insight]


class PersonalityIn(BaseModel):
    answers: list[int] = Field(min_length=5, max_length=200)


class PersonalityOut(BaseModel):
    openness: int
    conscientiousness: int
    extraversion: int
    agreeableness: int
    neuroticism: int
    summary: str | None
    created_at: datetime


class RecommendationOut(BaseModel):
    id: uuid.UUID
    major: str
    fit_score: int
    academic_fit: int
    personality_fit: int
    rationale: str | None
    universities: list | None
    admission_paths: list | None
    skills: list | None
    careers: list | None
    rank: int
    status: str


class MilestoneOut(ORMModel):
    id: uuid.UUID
    title: str
    description: str | None
    period: str
    position: int
    progress_percent: int
    status: str
    tasks: list | None


class MilestoneUpdate(BaseModel):
    progress_percent: int = Field(ge=0, le=100)


class ConsultationIn(BaseModel):
    counselor: str = Field(min_length=2, max_length=128)
    topic: str = Field(min_length=2, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)


class ConsultationOut(ORMModel):
    id: uuid.UUID
    counselor: str
    topic: str
    scheduled_at: datetime | None
    status: str
    notes: str | None
    created_at: datetime


class CounselorOut(BaseModel):
    """A school guidance counsellor (BK) that students can book."""

    name: str
    role: str
    focus: str


class ResourceOut(ORMModel):
    code: str
    category: str
    title: str
    description: str | None
    provider: str | None
    is_free: bool
    tags: list | None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatOut(BaseModel):
    answer: str
    confidence_bp: int
