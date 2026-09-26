"""Exam / question / attempt schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel

# Question kinds. ``essay`` is AI-graded free text; the rest are graded
# deterministically (instant) with no AI call.
QUESTION_TYPES = (
    "essay",
    "multiple_choice",
    "true_false",
    "multi_select",
    "numeric",
    "fill_blank",
    "matching",
    "ordering",
)
# Types that are graded deterministically (no AI provider).
AUTO_GRADED_TYPES = (
    "multiple_choice",
    "true_false",
    "multi_select",
    "numeric",
    "fill_blank",
    "matching",
    "ordering",
)
QTYPE_PATTERN = (
    "^(essay|multiple_choice|true_false|multi_select|numeric|fill_blank|matching|ordering)$"
)
MC_MIN_OPTIONS = 2
MC_MAX_OPTIONS = 8


class AnswerKeyIn(BaseModel):
    """Structured answer key for the non-single-label question types.

    All fields are optional; which ones are required depends on ``qtype``.
    """

    # multi_select: the correct option labels.
    correct: list[str] | None = None
    # numeric: the value and an absolute tolerance.
    value: float | None = None
    tolerance: float | None = None
    # fill_blank: accepted strings (case/space normalisation via flags).
    accepted: list[str] | None = None
    case_sensitive: bool = False
    trim: bool = True
    # matching/ordering: canonical order of the correct items (labels/keys).
    order: list[str] | None = None
    pairs: dict[str, str] | None = None


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


def _validate_question(
    qtype: str,
    options: list[OptionIn],
    correct_answer: str | None,
    key: AnswerKeyIn | None,
) -> None:
    """Per-type validation so an unsupported shape is rejected at the API edge."""
    if qtype == "multiple_choice":
        _validate_mc_options(options)
    elif qtype == "true_false":
        if (correct_answer or "").strip().lower() not in ("true", "false"):
            raise ValueError("true_false needs correct_answer 'true' or 'false'")
    elif qtype == "multi_select":
        if not (MC_MIN_OPTIONS <= len(options) <= MC_MAX_OPTIONS):
            raise ValueError(f"multi_select needs {MC_MIN_OPTIONS}–{MC_MAX_OPTIONS} options")
        correct = [o for o in options if o.is_correct]
        if len(correct) < 2:
            raise ValueError("multi_select needs at least two correct options")
    elif qtype == "numeric":
        if key is None or key.value is None:
            raise ValueError("numeric needs answer_json.value")
        if key.tolerance is not None and key.tolerance < 0:
            raise ValueError("numeric tolerance must be >= 0")
    elif qtype == "fill_blank":
        if key is None or not key.accepted:
            raise ValueError("fill_blank needs answer_json.accepted (non-empty)")
    elif qtype == "ordering":
        if key is None or not key.order or len(key.order) < 2:
            raise ValueError("ordering needs answer_json.order (>= 2 items)")
    elif qtype == "matching" and (key is None or not key.pairs or len(key.pairs) < 2):
        raise ValueError("matching needs answer_json.pairs (>= 2 pairs)")


class QuestionCreate(BaseModel):
    prompt: str = Field(min_length=5, max_length=10_000)
    correct_answer: str | None = Field(default=None, max_length=10_000)
    max_score_bp: int = Field(default=10_000, ge=0, le=10_000)
    position: int = Field(default=0, ge=0)
    qtype: str = Field(default="essay", pattern=QTYPE_PATTERN)
    options: list[OptionIn] = Field(default_factory=list)
    answer_json: AnswerKeyIn | None = None

    @model_validator(mode="after")
    def _check(self):
        _validate_question(self.qtype, self.options, self.correct_answer, self.answer_json)
        return self


class QuestionUpdate(BaseModel):
    prompt: str | None = Field(default=None, min_length=5, max_length=10_000)
    correct_answer: str | None = Field(default=None, max_length=10_000)
    max_score_bp: int | None = Field(default=None, ge=0, le=10_000)
    position: int | None = Field(default=None, ge=0)
    review_status: str | None = Field(default=None, pattern="^(pending|approved|rejected)$")
    qtype: str | None = Field(default=None, pattern=QTYPE_PATTERN)
    # When provided for a multiple_choice/multi_select question, replaces options.
    options: list[OptionIn] | None = None
    answer_json: AnswerKeyIn | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.options is not None and self.qtype in (None, "multiple_choice"):
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
    answer_json: dict | None = None


class AttachQuestionIn(BaseModel):
    """Copy an existing bank question into an exam."""

    question_id: uuid.UUID


class QuestionReorder(BaseModel):
    """A full, explicit question order to rewrite positions from."""

    question_ids: list[uuid.UUID] = Field(min_length=1)


class ExamCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    duration_minutes: int = Field(default=60, ge=1, le=600)
    room_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    passing_score_bp: int = Field(default=6000, ge=0, le=10_000)
    # Maximum attempts per student (0 = unlimited).
    max_attempts: int = Field(default=1, ge=0, le=100)
    shuffle_questions: bool = False
    shuffle_options: bool = False
    grace_seconds: int = Field(default=0, ge=0, le=3600)
    late_penalty_bp: int = Field(default=0, ge=0, le=10_000)
    instructions: str | None = Field(default=None, max_length=20_000)
    # Optional scheduling window. When set, attempts can only start within it
    # (students see 409 before `opens_at` / the deadline enforced at submit).
    opens_at: datetime | None = None
    closes_at: datetime | None = None


class ExamUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    passing_score_bp: int | None = Field(default=None, ge=0, le=10_000)
    max_attempts: int | None = Field(default=None, ge=0, le=100)
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None
    grace_seconds: int | None = Field(default=None, ge=0, le=3600)
    late_penalty_bp: int | None = Field(default=None, ge=0, le=10_000)
    instructions: str | None = Field(default=None, max_length=20_000)
    is_active: bool | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None


class ExamOut(ORMModel):
    id: uuid.UUID
    title: str
    owner_id: uuid.UUID
    room_id: uuid.UUID | None
    course_id: uuid.UUID | None
    duration_minutes: int
    max_attempts: int = 1
    shuffle_questions: bool = False
    shuffle_options: bool = False
    grace_seconds: int = 0
    late_penalty_bp: int = 0
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
    expires_at: datetime | None = None


class ExamResultRow(AttemptOut):
    """An attempt plus the student's display name (teacher results listing)."""

    display_name: str | None = None


class AnswerUpsert(BaseModel):
    answer_text: str = Field(max_length=20_000)


class OverrideAnswerIn(BaseModel):
    """Teacher/admin manual score override for a single answer."""

    score_bp: int = Field(ge=0, le=10_000)
    feedback: str | None = Field(default=None, max_length=2000)


class AttemptEventIn(BaseModel):
    """One proctoring telemetry sample from the client."""

    kind: str = Field(min_length=1, max_length=32)
    question_id: uuid.UUID | None = None
    detail: dict | None = None


class AttemptEventsIn(BaseModel):
    events: list[AttemptEventIn] = Field(default_factory=list, max_length=50)


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
    similarity_bp: int | None = None


class ExamResultReviewRow(ExamResultRow):
    """An attempt, the student's name, and their per-question answers."""

    answers: list[ReviewAnswerOut] = Field(default_factory=list)
    is_flagged: bool = False
    flag_reason: str | None = None
    violation_count: int = 0


class ExamResultsReviewOut(BaseModel):
    """Per-student answer review for a whole exam (teacher-only)."""

    exam: ExamOut
    results: list[ExamResultReviewRow] = Field(default_factory=list)
