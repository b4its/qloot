"""Career guidance schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class GradeIn(BaseModel):
    subject: str = Field(min_length=1, max_length=64)
    grade: int = Field(ge=0, le=100)
    term: str = Field(default="2025/2026-genap", max_length=32)


class GradeOut(ORMModel):
    id: uuid.UUID | None = None
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
    # A Big-Five Likert response per item — each answer must be 1..5.
    answers: list[Annotated[int, Field(ge=1, le=5)]] = Field(min_length=5, max_length=200)


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


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    period: str = Field(default="", max_length=64)
    tasks: list[str] = Field(default_factory=list)


class RoadmapReorder(BaseModel):
    ordered_ids: list[uuid.UUID] = Field(min_length=1)


class ConsultationIn(BaseModel):
    # CARE-06: book a real counselor user at a chosen slot. ``counselor`` is
    # kept as an optional free-text fallback for legacy clients.
    counselor_user_id: uuid.UUID | None = None
    counselor: str | None = Field(default=None, max_length=128)
    topic: str = Field(min_length=2, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)
    scheduled_at: datetime | None = None


class ConsultationOut(ORMModel):
    id: uuid.UUID
    counselor: str
    counselor_user_id: uuid.UUID | None = None
    topic: str
    scheduled_at: datetime | None
    status: str
    notes: str | None
    completed_at: datetime | None = None
    created_at: datetime


class ConsultationReschedule(BaseModel):
    scheduled_at: datetime


class ConsultationMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ConsultationMessageOut(ORMModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime


class CounselorOut(BaseModel):
    """A school guidance counsellor (BK) that students can book."""

    user_id: uuid.UUID | None = None
    name: str
    role: str
    # Free-text focus kept for the legacy display catalog.
    focus: str = ""


class PendingReviewOut(BaseModel):
    """A student whose study-path plan awaits the counselor's approval."""

    user_id: uuid.UUID
    display_name: str
    top_major: str
    count: int


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
    # Optional conversation to continue; omitted to start a new one (CARE-01).
    conversation_id: uuid.UUID | None = None


class ChatOut(BaseModel):
    answer: str
    confidence_bp: int = Field(ge=0, le=10_000)
    # Remaining ORT credit and free requests so the UI can show the meter.
    ort_balance: int = 0
    free_requests_remaining: int = 0
    # The conversation this turn belongs to (created if none was supplied).
    conversation_id: uuid.UUID | None = None


class AssistantMessageOut(ORMModel):
    id: uuid.UUID
    role: str
    content: str
    confidence_bp: int | None = None
    created_at: datetime


class AssistantConversationOut(ORMModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class AssistantConversationDetailOut(AssistantConversationOut):
    messages: list[AssistantMessageOut] = Field(default_factory=list)
