"""Exam / question / attempt schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel

# Question kinds. ``essay`` is AI-graded free text; ``multiple_choice`` is
# graded deterministically (instant) against the correct option.
QUESTION_TYPES = ("essay", "multiple_choice")
MC_MIN_OPTIONS = 2
MC_MAX_OPTIONS = 8


class OptionIn(BaseModel):
    """A choice for a multiple-choice question."""

    text: str = Field(min_length=1, max_length=1000)
    is_correct: bool = False
    # Optional explicit label (A, B, C…). Server assigns one when omitted.
    label: str | None = Field(default=None, max_length=8)


class OptionOut(BaseModel):
    id: uuid.UUID
    label: str
    text: str
    position: int
    # Only revealed to the exam owner/admin; students get ``None``.
    is_correct: bool | None = None


def _validate_mc_options(options: list[OptionIn]) -> list[OptionIn]:
    if not (MC_MIN_OPTIONS <= len(options) <= MC_MAX_OPTIONS):
        raise ValueError(f"multiple_choice needs {MC_MIN_OPTIONS}–{MC_MAX_OPTIONS} options")
    correct = [o for o in options if o.is_correct]
    if len(correct) != 1:
        raise ValueError("multiple_choice needs exactly one correct option")
    return options


class QuestionCreate(BaseModel):
    prompt: str = Field(min_length=5)
    correct_answer: str | None = None
    max_score_bp: int = Field(default=10_000, ge=0, le=10_000)
    position: int = 0
    qtype: str = Field(default="essay", pattern="^(essay|multiple_choice)$")
    options: list[OptionIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self):
        if self.qtype == "multiple_choice":
            _validate_mc_options(self.options)
        return self


class QuestionUpdate(BaseModel):
    prompt: str | None = Field(default=None, min_length=5)
    correct_answer: str | None = None
    max_score_bp: int | None = Field(default=None, ge=0, le=10_000)
    position: int | None = None
    review_status: str | None = Field(default=None, pattern="^(pending|approved|rejected)$")
    # When provided for a multiple_choice question, replaces all options.
    options: list[OptionIn] | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.options is not None:
            _validate_mc_options(self.options)
        return self


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
    options: list[OptionOut] = Field(default_factory=list)


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
    # Question composition, so the UI can classify an exam as multiple-choice,
    # essay or mixed without fetching every question.
    question_count: int = 0
    mc_count: int = 0
    essay_count: int = 0


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


class ExamResultRow(AttemptOut):
    """An attempt plus the student's display name (teacher results listing)."""

    display_name: str | None = None


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
    # Always returned so the result page renders even before grading / after the
    # exam is closed.
    exam: ExamOut
    answers: list[AnswerOut]
    # Questions with the answer key revealed for review (only populated once the
    # attempt is graded, so a student can see which choice was correct).
    questions: list[QuestionOut] = Field(default_factory=list)


class ReviewAnswerOut(BaseModel):
    """One answered question inside a per-student exam review.

    ``is_correct`` is only meaningful for multiple-choice (``score_bp ==
    max_score_bp``); it is ``None`` for essays and for ungraded attempts.
    """

    question_id: uuid.UUID
    position: int
    qtype: str
    prompt: str
    answer_text: str | None  # raw (MC: the chosen option label)
    answer_display: str | None  # resolved option text for MC; else answer_text
    correct_answer: str | None  # MC: the correct option label
    correct_display: str | None  # MC: the correct option text
    is_correct: bool | None
    score_bp: int | None
    max_score_bp: int
    feedback: str | None


class ExamResultReviewRow(ExamResultRow):
    """An attempt, the student's name, and their per-question answers."""

    answers: list[ReviewAnswerOut] = Field(default_factory=list)


class ExamResultsReviewOut(BaseModel):
    """Per-student answer review for a whole exam (teacher-only)."""

    exam: ExamOut
    results: list[ExamResultReviewRow] = Field(default_factory=list)
