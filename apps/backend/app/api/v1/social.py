"""Notification & badge endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, CurrentUser, DbSession, LimitParam, OffsetParam
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
    user: CurrentUser,
    db: DbSession,
    unread_only: bool = False,
    limit: LimitParam = 50,
    offset: OffsetParam = 0,
):
    return await NotificationService(db).list_for_user(
        user.id, limit=limit, offset=offset, unread_only=unread_only
    )


@router.get("/notifications/unread-count", response_model=UnreadCount)
async def unread_count(user: CurrentUser, db: DbSession):
    return UnreadCount(unread=await NotificationService(db).unread_count(user.id))


@router.get("/notifications/preferences")
async def get_notification_preferences(user: CurrentUser, db: DbSession):
    """The caller's muted notification kinds (opt-out; absent = all enabled)."""
    from app.models.social import NotificationPreference

    pref = await db.get(NotificationPreference, user.id)
    return {"muted_kinds": pref.muted_kinds if pref else []}


@router.put("/notifications/preferences")
async def set_notification_preferences(payload: dict, user: CurrentUser, db: DbSession):
    """Replace the caller's muted-kinds set.

    Body: ``{"muted_kinds": ["quest", "level"]}``. An empty list re-enables
    every kind.
    """
    from app.core.errors import ValidationError
    from app.models.social import NotificationPreference

    muted = payload.get("muted_kinds")
    if not isinstance(muted, list) or not all(isinstance(k, str) for k in muted):
        raise ValidationError("muted_kinds must be a list of strings")
    async with transaction(db):
        pref = await db.get(NotificationPreference, user.id)
        if pref is None:
            pref = NotificationPreference(user_id=user.id, muted_kinds=muted)
            db.add(pref)
        else:
            pref.muted_kinds = muted
        await db.flush()
    return {"muted_kinds": muted}


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
async def my_badges(
    user: CurrentUser, db: DbSession, limit: LimitParam = 200, offset: OffsetParam = 0
):
    rows = await BadgeService(db).list_for_user(user.id, limit=limit, offset=offset)
    return [
        UserBadgeOut(badge=BadgeOut.model_validate(badge), awarded_at=ub.awarded_at, meta=ub.meta)
        for ub, badge in rows
    ]
