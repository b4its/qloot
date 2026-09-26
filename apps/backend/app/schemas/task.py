"""Task schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field, model_validator

from app.schemas.common import ORMModel


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    kind: str = Field(default="daily", pattern="^(daily|weekly|learning|exam)$")
    reward_amount: int = Field(default=0, ge=0, le=1_000_000)
    course_id: uuid.UUID | None = None
    quest_id: uuid.UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _window_ordered(self) -> TaskCreate:
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    kind: str | None = Field(default=None, pattern="^(daily|weekly|learning|exam)$")
    reward_amount: int | None = Field(default=None, ge=0, le=1_000_000)
    is_active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def _window_ordered(self) -> TaskUpdate:
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class TaskOut(ORMModel):
    id: uuid.UUID
    title: str
    description: str | None
    kind: str
    reward_amount: int
    course_id: uuid.UUID | None
    quest_id: uuid.UUID | None
    is_active: bool
    starts_at: datetime | None
    ends_at: datetime | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def honor_system(self) -> bool:
        """True when completion is pure self-report (no course/quest binding
        to verify against). Surfaced so the UI can label the difference.
        """
        return self.course_id is None and self.quest_id is None


class TaskCompletionOut(ORMModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    reward_key: str
    completed_at: datetime
