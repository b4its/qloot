"""Authentication endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.errors import AuthError
from app.db.session import transaction
from app.schemas.auth import (
    ForgotPasswordOut,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionOut,
    UserOut,
)
from app.schemas.common import Message
from app.services.auth_service import AuthService

router = APIRouter()


def _user_out(user) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        chain_user_ref=user.chain_user_ref,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        roles=sorted(user.role_names),
        class_code=user.class_code,
        class_type=user.class_type,
    )


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_secure,
        samesite=settings.session_same_site,
        max_age=settings.session_ttl_seconds,
        domain=settings.session_cookie_domain,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, request: Request, response: Response, db: DbSession
) -> UserOut:
    async with transaction(db):
        service = AuthService(db)
        user, token = await service.register(
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            role=payload.role,
            class_code=payload.class_code,
            class_type=payload.class_type,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    _set_session_cookie(response, token)
    return _user_out(user)


@router.post("/login", response_model=UserOut)
async def login(
    payload: LoginRequest, request: Request, response: Response, db: DbSession
) -> UserOut:
    service = AuthService(db)
    user, token = await service.login(
        email=payload.email,
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    # Commit the successful session + reset counters in one step.
    await db.commit()
    user = await service.users.get_with_roles(user.id) or user
    _set_session_cookie(response, token)
    return _user_out(user)


@router.post("/logout", response_model=Message)
async def logout(request: Request, response: Response, db: DbSession) -> Message:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        async with transaction(db):
            await AuthService(db).logout(token)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return Message(message="Logged out")


@router.post("/refresh", response_model=UserOut)
async def refresh(request: Request, response: Response, db: DbSession) -> UserOut:
    """Rotate the session token (revoke old, issue new)."""
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AuthError("No active session")
    async with transaction(db):
        service = AuthService(db)
        user = await _user_from_token(service, token)
        await service.logout(token)
        new_token = await service._issue_session(  # noqa: SLF001
            user,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    _set_session_cookie(response, new_token)
    return _user_out(user)


async def _user_from_token(service: AuthService, token: str):
    from sqlalchemy import select

    from app.core.security import hash_session_token
    from app.models.identity import User

    token_hash = hash_session_token(token, settings.session_secret)
    session = await service.sessions.get_by_token_hash(token_hash)
    if session is None:
        raise AuthError("Invalid session")
    user = (
        await service.session.execute(select(User).where(User.id == session.user_id))
    ).scalar_one_or_none()
    if user is None:
        raise AuthError("Invalid session")
    return user


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return _user_out(user)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(user: CurrentUser, db: DbSession) -> list[SessionOut]:
    sessions = await AuthService(db).list_sessions(user.id)
    return [SessionOut.model_validate(s) for s in sessions]


@router.delete("/sessions/{session_id}", response_model=Message)
async def revoke_session(session_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Message:
    async with transaction(db):
        await AuthService(db).revoke_session(user.id, session_id)
    return Message(message="Session revoked")


@router.post("/forgot-password", response_model=ForgotPasswordOut)
async def forgot_password(payload: ForgotPasswordRequest, db: DbSession) -> ForgotPasswordOut:
    token: str | None = None
    async with transaction(db):
        token = await AuthService(db).request_password_reset(payload.email)
    # Always return the same message to avoid account enumeration. Outside
    # production we also return the raw token so the simulated reset flow can be
    # completed without an email server.
    return ForgotPasswordOut(
        message="If the account exists, a reset link has been sent",
        reset_token=None if settings.is_production else token,
    )


@router.post("/reset-password", response_model=Message)
async def reset_password(payload: ResetPasswordRequest, db: DbSession) -> Message:
    async with transaction(db):
        await AuthService(db).reset_password(payload.token, payload.new_password)
    return Message(message="Password has been reset")
