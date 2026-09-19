"""Material schemas + AI job schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class MaterialOut(ORMModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    course_id: uuid.UUID | None
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    status: str
    created_at: datetime


class GenerateQuestionsRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=20)
    language: str = Field(default="id", max_length=8)
    exam_id: uuid.UUID | None = None


class AIJobOut(ORMModel):
    id: uuid.UUID
    kind: str
    status: str
    attempts: int
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class GeneratedQuestionOut(BaseModel):
    id: uuid.UUID
    prompt: str
    correct_answer: str | None
    max_score_bp: int
    review_status: str


class GradeRequest(BaseModel):
    attempt_id: uuid.UUID


class GradedItemOut(BaseModel):
    question_id: uuid.UUID
    score_bp: int | None
    feedback: str | None
    similarity_bp: int | None


class SummaryOut(BaseModel):
    summary: str
    key_points: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    language: str = Field(default="id", max_length=8)


class AnswerOut(BaseModel):
    answer: str
    confidence_bp: int
