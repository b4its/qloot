"""Quest schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class QuestRuleIn(BaseModel):
    rank: int = Field(ge=1, le=100)
    reward_amount: int = Field(ge=0)
    min_score_bp: int | None = Field(default=None, ge=0, le=10_000)


class QuestCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    room_id: uuid.UUID | None = None
    exam_id: uuid.UUID | None = None
    kind: str = Field(default="exam", pattern="^(exam|quiz|task)$")
    top_n_winners: int = Field(default=3, ge=1, le=50)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    rules: list[QuestRuleIn] = Field(default_factory=list)


class QuestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    top_n_winners: int | None = Field(default=None, ge=1, le=50)
    opens_at: datetime | None = None
    closes_at: datetime | None = None


class QuestRuleOut(ORMModel):
    rank: int
    reward_amount: int
    min_score_bp: int | None


class QuestOut(ORMModel):
    id: uuid.UUID
    title: str
    description: str | None
    owner_id: uuid.UUID
    room_id: uuid.UUID | None
    exam_id: uuid.UUID | None
    status: str
    kind: str
    top_n_winners: int
    reward_version: int
    opens_at: datetime | None
    closes_at: datetime | None
    finalized_at: datetime | None
    created_at: datetime


class QuestDetailOut(QuestOut):
    rules: list[QuestRuleOut] = Field(default_factory=list)


class WinnerOut(BaseModel):
    rank: int
    user_id: uuid.UUID
    score_bp: int
    submitted_at: datetime
    reward_key: str
    reward_amount: int


class FinalizeResult(BaseModel):
    quest_id: uuid.UUID
    winners: list[WinnerOut]
    allocations_created: int
