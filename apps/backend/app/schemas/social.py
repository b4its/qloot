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


class MarkReadBatch(BaseModel):
    """Body for marking a caller-chosen set of notifications read (STUDY-09)."""

    ids: list[uuid.UUID] = Field(default_factory=list)


class NotificationPage(BaseModel):
    """Paginated notification feed with the counters the UI needs in one call.

    Bundling the totals with the page avoids a second round-trip and keeps the
    filter chips (per-kind counts) consistent with the visible items.
    """

    items: list[NotificationOut]
    total: int
    unread: int
    kind_counts: dict[str, int] = Field(default_factory=dict)


class BadgeOut(ORMModel):
    code: str
    name: str
    description: str | None = None
    icon: str
    points: int
    rarity: str


class UserBadgeOut(BaseModel):
    badge: BadgeOut
    awarded_at: datetime
    meta: dict | None = None


class BadgeProgressOut(BaseModel):
    """A catalogued badge plus the caller's progress toward unlocking it."""

    badge: BadgeOut
    current: int
    target: int
    unlocked: bool


class NotificationCreate(BaseModel):
    """Admin/broadcast notification."""

    title: str = Field(min_length=1, max_length=255)
    body: str | None = None
    kind: str = "system"
    user_ids: list[uuid.UUID] | None = None  # None = all active users


class FollowStatusOut(BaseModel):
    """Follow relationship between the viewer and a target user (COMM-06)."""

    user_id: uuid.UUID
    followers: int
    following: int
    is_following: bool
