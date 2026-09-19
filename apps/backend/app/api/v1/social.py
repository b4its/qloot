"""Notification & badge endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.db.session import transaction
from app.schemas.common import Message
from app.schemas.social import (
    BadgeOut,
    NotificationCreate,
    NotificationOut,
    UnreadCount,
    UserBadgeOut,
)
from app.services.social_service import BadgeService, NotificationService

router = APIRouter()


# --- notifications ---------------------------------------------------------
@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    user: CurrentUser, db: DbSession, unread_only: bool = False, limit: int = 50, offset: int = 0
):
    return await NotificationService(db).list_for_user(
        user.id, limit=limit, offset=offset, unread_only=unread_only
    )


@router.get("/notifications/unread-count", response_model=UnreadCount)
async def unread_count(user: CurrentUser, db: DbSession):
    return UnreadCount(unread=await NotificationService(db).unread_count(user.id))


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
async def mark_read(notification_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await NotificationService(db).mark_read(user.id, notification_id)


@router.post("/notifications/read-all", response_model=Message)
async def mark_all_read(user: CurrentUser, db: DbSession):
    async with transaction(db):
        n = await NotificationService(db).mark_all_read(user.id)
    return Message(message=f"{n} notifications marked as read")


@router.post("/admin/notifications", response_model=Message, status_code=status.HTTP_201_CREATED)
async def broadcast(admin: AdminUser, db: DbSession, payload: NotificationCreate):
    from sqlalchemy import select

    from app.models.identity import User

    async with transaction(db):
        if payload.user_ids:
            targets = payload.user_ids
        else:
            rows = await db.execute(select(User.id).where(User.is_active.is_(True)))
            targets = list(rows.scalars().all())
        count = await NotificationService(db).notify_many(
            user_ids=targets, kind=payload.kind, title=payload.title, body=payload.body
        )
    return Message(message=f"Sent to {count} users")


# --- badges ----------------------------------------------------------------
@router.get("/badges", response_model=list[BadgeOut])
async def badge_catalog(user: CurrentUser, db: DbSession):
    async with transaction(db):
        await BadgeService(db).ensure_catalog()
        badges = await BadgeService(db).catalog()
    return badges


@router.get("/me/badges", response_model=list[UserBadgeOut])
async def my_badges(user: CurrentUser, db: DbSession):
    rows = await BadgeService(db).list_for_user(user.id)
    return [
        UserBadgeOut(badge=BadgeOut.model_validate(badge), awarded_at=ub.awarded_at, meta=ub.meta)
        for ub, badge in rows
    ]
