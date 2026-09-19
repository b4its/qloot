"""Room schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RoomCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    course_id: uuid.UUID | None = None
    max_participants: int = Field(default=100, ge=2, le=1000)
    is_public: bool = True


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    max_participants: int | None = Field(default=None, ge=2, le=1000)
    is_public: bool | None = None


class RoomOut(ORMModel):
    id: uuid.UUID
    name: str
    code: str
    owner_id: uuid.UUID
    course_id: uuid.UUID | None
    status: str
    max_participants: int
    is_public: bool
    opens_at: datetime | None
    closes_at: datetime | None
    created_at: datetime


class RoomMemberOut(ORMModel):
    id: uuid.UUID
    room_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    is_present: bool
    joined_at: datetime


class JoinByCode(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class LiveEntry(BaseModel):
    rank: int
    user_id: uuid.UUID
    score_bp: int
    is_present: bool


class RoomEventOut(ORMModel):
    id: uuid.UUID
    event_type: str
    payload: dict | None = None
    created_at: datetime


class InviteCreate(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    note: str | None = Field(default=None, max_length=255)


class InviteOut(ORMModel):
    id: uuid.UUID
    room_id: uuid.UUID
    email: str | None
    code: str
    accepted_at: datetime | None
    created_at: datetime


class AcceptInvite(BaseModel):
    code: str = Field(min_length=4, max_length=32)
