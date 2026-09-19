"""Task schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    kind: str = "daily"
    reward_amount: int = Field(default=0, ge=0)
    course_id: uuid.UUID | None = None
    quest_id: uuid.UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    reward_amount: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    ends_at: datetime | None = None


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


class TaskCompletionOut(ORMModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    reward_key: str
    completed_at: datetime
