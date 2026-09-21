"""Shared FastAPI dependencies: DB session, current user, role guards."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AuthError, ForbiddenError
from app.core.security import hash_session_token
from app.db.session import get_db
from app.models.identity import Session as SessionModel
from app.models.identity import User

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Bounded pagination so a client cannot request an unbounded (or negative) page.
LimitParam = Annotated[int, Query(ge=1, le=200)]
OffsetParam = Annotated[int, Query(ge=0, le=1_000_000)]


def _extract_session_token(request: Request) -> str | None:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        return token
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def get_current_user_optional(request: Request, db: DbSession) -> User | None:
    token = _extract_session_token(request)
    if not token:
        return None
    token_hash = hash_session_token(token, settings.session_secret)
    stmt = (
        select(SessionModel)
        .where(SessionModel.token_hash == token_hash)
        .where(SessionModel.revoked_at.is_(None))
        .where(SessionModel.expires_at > datetime.now(UTC))
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        return None
    user = (await db.execute(select(User).where(User.id == session.user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    session.last_used_at = datetime.now(UTC)
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


async def get_current_user(request: Request, db: DbSession) -> User:
    user = await get_current_user_optional(request, db)
    if user is None:
        raise AuthError("Authentication required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


def require_roles(*roles: str):
    async def _guard(user: CurrentUser) -> User:
        if user.has_role("admin") or user.has_role(*roles):
            return user
        raise ForbiddenError(f"Requires one of roles: {', '.join(roles)}")

    return _guard


def ensure_owner_or_admin(owner_id: uuid.UUID, user: User) -> None:
    """Object-level authorization: owner OR admin, never by id alone."""
    if user.has_role("admin"):
        return
    if owner_id != user.id:
        raise ForbiddenError("You do not own this resource")


TeacherUser = Annotated[User, Depends(require_roles("teacher"))]
AdminUser = Annotated[User, Depends(require_roles("admin"))]
StaffUser = Annotated[User, Depends(require_roles("teacher"))]
