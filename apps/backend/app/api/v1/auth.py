"""Authentication endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam
from app.core.config import settings
from app.core.errors import AuthError, ValidationError
from app.db.session import transaction
from app.middleware.rate_limit import rate_limit
from app.schemas.auth import (
    ChangeEmailOut,
    ChangeEmailRequest,
    ChangePasswordRequest,
    ConfirmEmailChangeRequest,
    ForgotPasswordOut,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionOut,
    UserOut,
)
from app.schemas.common import Message
from app.services.auth_service import AuthService
from app.services.storage import sniff_image, storage

router = APIRouter()


def _user_out(user, session_expires_at=None) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        chain_user_ref=user.chain_user_ref,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        roles=sorted(user.role_names),
        class_code=user.class_code,
        class_type=user.class_type,
        session_expires_at=session_expires_at,
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


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register"))],
)
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


@router.post("/login", response_model=UserOut, dependencies=[Depends(rate_limit("login"))])
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
    response.delete_cookie(
        settings.session_cookie_name, path="/", domain=settings.session_cookie_domain
    )
    return Message(message="Logged out")


@router.post("/logout-all", response_model=Message)
async def logout_all(user: CurrentUser, response: Response, db: DbSession) -> Message:
    """Revoke every session for the caller (sign out everywhere), including
    the one making this request — the cookie is cleared client-side too.
    """
    async with transaction(db):
        await AuthService(db).logout_all(user.id)
    response.delete_cookie(
        settings.session_cookie_name, path="/", domain=settings.session_cookie_domain
    )
    return Message(message="Signed out of all devices")


@router.post("/refresh", response_model=UserOut)
async def refresh(request: Request, response: Response, db: DbSession) -> UserOut:
    """Rotate the session token (revoke old, issue new)."""
    from app.core.security import hash_session_token
    from app.repositories.users import SessionRepository

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
        new_session = await SessionRepository(db).get_by_token_hash(
            hash_session_token(new_token, settings.session_secret)
        )
        expires_at = new_session.expires_at if new_session else None
    _set_session_cookie(response, new_token)
    return _user_out(user, expires_at)


async def _user_from_token(service: AuthService, token: str):
    from sqlalchemy import select

    from app.core.security import hash_session_token
    from app.models.identity import User

    token_hash = hash_session_token(token, settings.session_secret)
    session = await service.sessions.get_by_token_hash(token_hash)
    if session is None or session.revoked_at is not None or session.expires_at <= datetime.now(UTC):
        raise AuthError("Invalid session")
    user = (
        await service.session.execute(select(User).where(User.id == session.user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError("Invalid session")
    return user


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser, request: Request, db: DbSession) -> UserOut:
    # Surface the current session's expiry so the client can rotate the token
    # before it lapses (AUTH-10) instead of being logged out mid-session.
    from app.core.security import hash_session_token
    from app.repositories.users import SessionRepository

    expires_at = None
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        session = await SessionRepository(db).get_by_token_hash(
            hash_session_token(token, settings.session_secret)
        )
        if session is not None:
            expires_at = session.expires_at
    return _user_out(user, expires_at)


@router.get("/export")
async def export_my_data(user: CurrentUser, db: DbSession) -> Response:
    """Return a portable JSON export of the caller's own data (W5).

    A self-service data portability endpoint: the authenticated user downloads
    everything the platform stores about *them* (profile, learning progress,
    exam attempts, wallet ledger, badges, certificates). No other user's data is
    included and no secrets (password hash, session tokens) are exposed.
    """
    from sqlalchemy import select

    from app.models.certificate import Certificate
    from app.models.exam import ExamAttempt
    from app.models.learning import LessonProgress
    from app.models.social import Badge, UserBadge
    from app.models.wallet import WalletAccount, WalletLedgerEntry

    export: dict = {
        "exported_at": datetime.now(UTC).isoformat(),
        "schema_version": 1,
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "class_code": user.class_code,
            "class_type": user.class_type,
            "chain_user_ref": user.chain_user_ref,
            "roles": sorted(user.role_names) if user.role_names else [],
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
    }

    progress_rows = (
        await db.execute(select(LessonProgress).where(LessonProgress.user_id == user.id))
    ).scalars().all()
    export["learning_progress"] = [
        {
            "course_id": str(p.course_id),
            "lesson_id": str(p.lesson_id),
            "progress_percent": p.progress_percent,
            "completed": p.completed,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        }
        for p in progress_rows
    ]

    attempt_rows = (
        await db.execute(select(ExamAttempt).where(ExamAttempt.user_id == user.id))
    ).scalars().all()
    export["exam_attempts"] = [
        {
            "id": str(a.id),
            "exam_id": str(a.exam_id),
            "attempt_number": a.attempt_number,
            "status": a.status,
            "score_bp": a.score_bp,
            "passed": a.passed,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        }
        for a in attempt_rows
    ]

    badge_rows = (
        await db.execute(
            select(UserBadge, Badge.code)
            .join(Badge, Badge.id == UserBadge.badge_id)
            .where(UserBadge.user_id == user.id)
        )
    ).all()
    export["badges"] = [
        {
            "code": code,
            "awarded_at": ub.awarded_at.isoformat() if ub.awarded_at else None,
        }
        for ub, code in badge_rows
    ]

    account = (
        await db.execute(select(WalletAccount).where(WalletAccount.user_id == user.id))
    ).scalar_one_or_none()
    if account is not None:
        ledger_rows = (
            await db.execute(
                select(WalletLedgerEntry)
                .where(WalletLedgerEntry.account_id == account.id)
                .order_by(WalletLedgerEntry.created_at)
            )
        ).scalars().all()
        export["wallet"] = {
            "token_id": account.token_id,
            "withdrawal_address": account.withdrawal_address,
            "entries": [
                {
                    "entry_type": e.entry_type,
                    "amount": e.amount,
                    "balance_after": e.balance_after,
                    "reference_type": e.reference_type,
                    "description": e.description,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in ledger_rows
            ],
        }

    cert_rows = (
        await db.execute(select(Certificate).where(Certificate.user_id == user.id))
    ).scalars().all()
    export["certificates"] = [
        {
            "credential_id": c.credential_id,
            "course_title": c.course_title,
            "issued_at": c.issued_at.isoformat() if c.issued_at else None,
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        }
        for c in cert_rows
    ]

    payload = json.dumps(export, ensure_ascii=False, indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="qloot-export-{user.id}.json"'
        },
    )


@router.patch("/profile", response_model=UserOut)
async def update_profile(
    payload: ProfileUpdateRequest, user: CurrentUser, db: DbSession
) -> UserOut:
    async with transaction(db):
        updated = await AuthService(db).update_profile(user, full_name=payload.full_name)
    return _user_out(updated)


@router.post("/profile/avatar", response_model=UserOut)
async def upload_avatar(user: CurrentUser, db: DbSession, file: UploadFile = File(...)) -> UserOut:
    """Upload/replace the caller's avatar image (AUTH-04).

    Reused validation posture from material uploads: size-capped read, magic-
    byte sniff (not just the client Content-Type), and a hardened storage key
    the caller cannot influence beyond the extension.
    """
    content = await file.read(settings.avatar_max_bytes + 1)
    if len(content) > settings.avatar_max_bytes:
        raise ValidationError(f"Avatar exceeds the {settings.avatar_max_bytes} byte limit")
    content_type = sniff_image(content)
    if content_type is None:
        raise ValidationError("File is not a recognised image (png/jpeg/webp)")
    key = f"avatars/{user.id}/{uuid.uuid4().hex}.{content_type.split('/')[-1]}"
    storage.put(key, content, content_type)
    async with transaction(db):
        updated = await AuthService(db).update_profile(user, avatar_url=key)
    return _user_out(updated)


@router.get("/avatars/{user_id}")
async def get_avatar(user_id: uuid.UUID, db: DbSession):
    """Serve a user's avatar image (public — avatars are not sensitive).

    302s to a presigned URL when using object storage; streams directly for
    local storage, mirroring the materials download endpoint's fallback.
    """
    from fastapi import Response
    from fastapi.responses import RedirectResponse

    from app.core.errors import NotFoundError
    from app.models.identity import User

    user = await db.get(User, user_id)
    if user is None or not user.avatar_url:
        raise NotFoundError("Avatar not found")
    key = user.avatar_url
    presigned = storage.presigned_get_url(key, expires_seconds=300)
    if presigned is not None:
        return RedirectResponse(url=presigned, status_code=302)
    data = storage.get(key)
    ext = key.rsplit(".", 1)[-1].lower()
    content_types = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }
    content_type = content_types.get(ext, "application/octet-stream")
    return Response(content=data, media_type=content_type)


@router.post(
    "/change-email/request",
    response_model=ChangeEmailOut,
    dependencies=[Depends(rate_limit("password_reset"))],
)
async def request_change_email(
    payload: ChangeEmailRequest, user: CurrentUser, db: DbSession
) -> ChangeEmailOut:
    async with transaction(db):
        token = await AuthService(db).request_email_change(user, payload.new_email)
    return ChangeEmailOut(
        message="Verification link sent to the new address",
        change_token=None if settings.is_production else token,
    )


@router.post("/change-email/confirm", response_model=UserOut)
async def confirm_change_email(payload: ConfirmEmailChangeRequest, db: DbSession) -> UserOut:
    async with transaction(db):
        user = await AuthService(db).confirm_email_change(payload.token)
    return _user_out(user)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
) -> list[SessionOut]:
    sessions = await AuthService(db).list_sessions(user.id, limit=limit, offset=offset)
    return [SessionOut.model_validate(s) for s in sessions]


@router.delete("/sessions/{session_id}", response_model=Message)
async def revoke_session(session_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Message:
    async with transaction(db):
        await AuthService(db).revoke_session(user.id, session_id)
    return Message(message="Session revoked")


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordOut,
    dependencies=[Depends(rate_limit("password_reset"))],
)
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


@router.post(
    "/reset-password",
    response_model=Message,
    dependencies=[Depends(rate_limit("password_reset"))],
)
async def reset_password(payload: ResetPasswordRequest, db: DbSession) -> Message:
    async with transaction(db):
        await AuthService(db).reset_password(payload.token, payload.new_password)
    return Message(message="Password has been reset")


@router.post(
    "/change-password",
    response_model=Message,
    dependencies=[Depends(rate_limit("password_reset"))],
)
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    request: Request,
    db: DbSession,
) -> Message:
    """Change the password for the currently logged-in user.

    Requires the current password; revokes every *other* session, keeping
    the caller's own session (the one making this request) alive.
    """
    from app.core.security import hash_session_token

    token = request.cookies.get(settings.session_cookie_name)
    keep_hash = hash_session_token(token, settings.session_secret) if token else None
    async with transaction(db):
        await AuthService(db).change_password(
            user,
            current_password=payload.current_password,
            new_password=payload.new_password,
            keep_session_token_hash=keep_hash,
        )
    return Message(message="Password changed")
