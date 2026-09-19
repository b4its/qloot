"""Notification & badge schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class NotificationOut(ORMModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str | None
    data: dict | None = None
    read_at: datetime | None = None
    created_at: datetime


class UnreadCount(BaseModel):
    unread: int


class BadgeOut(ORMModel):
    code: str
    name: str
    description: str | None = None
    icon: str
    points: int


class UserBadgeOut(BaseModel):
    badge: BadgeOut
    awarded_at: datetime
    meta: dict | None = None


class NotificationCreate(BaseModel):
    """Admin/broadcast notification."""

    title: str = Field(min_length=1, max_length=255)
    body: str | None = None
    kind: str = "system"
    user_ids: list[uuid.UUID] | None = None  # None = all active users
