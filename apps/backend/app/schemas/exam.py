"""Exam / question / attempt schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class QuestionCreate(BaseModel):
    prompt: str = Field(min_length=5)
    correct_answer: str | None = None
    max_score_bp: int = Field(default=10_000, ge=0, le=10_000)
    position: int = 0
    qtype: str = "essay"


class QuestionUpdate(BaseModel):
    prompt: str | None = Field(default=None, min_length=5)
    correct_answer: str | None = None
    max_score_bp: int | None = Field(default=None, ge=0, le=10_000)
    position: int | None = None
    review_status: str | None = Field(default=None, pattern="^(pending|approved|rejected)$")


class QuestionOut(ORMModel):
    id: uuid.UUID
    exam_id: uuid.UUID | None
    prompt: str
    correct_answer: str | None
    max_score_bp: int
    position: int
    qtype: str
    source: str
    review_status: str


class ExamCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    duration_minutes: int = Field(default=60, ge=1, le=600)
    room_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    year: int | None = None
    passing_score_bp: int = Field(default=6000, ge=0, le=10_000)
    instructions: str | None = None


class ExamUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    passing_score_bp: int | None = Field(default=None, ge=0, le=10_000)
    instructions: str | None = None
    is_active: bool | None = None


class ExamOut(ORMModel):
    id: uuid.UUID
    title: str
    owner_id: uuid.UUID
    room_id: uuid.UUID | None
    course_id: uuid.UUID | None
    duration_minutes: int
    status: str
    is_active: bool
    passing_score_bp: int
    opens_at: datetime | None
    closes_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExamDetailOut(ExamOut):
    questions: list[QuestionOut] = Field(default_factory=list)


class AttemptOut(ORMModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    user_id: uuid.UUID
    attempt_number: int
    status: str
    score_bp: int | None
    passed: bool | None
    started_at: datetime
    submitted_at: datetime | None
    graded_at: datetime | None


class AnswerUpsert(BaseModel):
    answer_text: str = Field(max_length=20_000)


class AnswerOut(ORMModel):
    id: uuid.UUID
    question_id: uuid.UUID
    answer_text: str | None
    score_bp: int | None
    max_score_bp: int
    feedback: str | None
    similarity_bp: int | None


class AttemptResultOut(BaseModel):
    attempt: AttemptOut
    answers: list[AnswerOut]
