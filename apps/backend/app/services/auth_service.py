"""Authentication service: register, login, sessions, password reset."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AuthError, ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    needs_rehash,
    verify_password,
)
from app.models.identity import PasswordResetToken, User
from app.models.identity import Session as SessionModel
from app.models.wallet import WalletAccount
from app.repositories.users import SessionRepository, UserRepository

log = get_logger("auth")


def _compute_chain_user_ref(secret: str, user_id: uuid.UUID) -> str:
    """Salt+hash a user id into an opaque 32-byte ref for on-chain events."""
    mac = hmac.new(secret.encode(), str(user_id).encode(), hashlib.sha256)
    return "0x" + mac.hexdigest()


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)

    async def register(
        self,
        *,
        email: str,
        full_name: str,
        password: str,
        role: str = "student",
        class_code: str | None = None,
        class_type: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, str]:
        existing = await self.users.get_by_email(email)
        if existing is not None:
            raise ConflictError("Email already registered")

        import uuid as _uuid  # noqa

        from app.services.course_service import normalize_class_code, normalize_class_type

        user_id = _uuid.uuid4()
        user = User(
            id=user_id,
            email=email.lower(),
            full_name=full_name,
            password_hash=hash_password(password),
            chain_user_ref=_compute_chain_user_ref(settings.session_secret, user_id),
            class_code=normalize_class_code(class_code) if class_code else None,
            class_type=normalize_class_type(class_type),
        )
        await self.users.add(user)
        await self.users.assign_role(user, role)

        # Every user gets a custodial wallet account (double-entry ledger).
        self.session.add(WalletAccount(user_id=user.id, token_id=settings.opc_token_id))

        # Welcome notification.
        from app.services.social_service import NotificationService

        await NotificationService(self.session).notify(
            user_id=user.id,
            kind="system",
            title="Welcome to QLoot! 🎉",
            body="Start learning, join rooms and complete quests to earn OryphemCoin.",
        )

        await self.session.flush()
        fresh = await self.users.get_with_roles(user.id)
        user = fresh or user

        token = await self._issue_session(user, user_agent=user_agent, ip_address=ip_address)
        log.info("user_registered", user_id=str(user.id), role=role)
        return user, token

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, str]:
        user = await self.users.get_by_email(email)
        now = datetime.now(UTC)

        if user is None:
            # Constant-ish work to reduce user enumeration timing signal.
            hash_password("dummy-password-for-timing")
            raise AuthError("Invalid credentials")

        if user.locked_until is not None and user.locked_until > now:
            raise AuthError("Account temporarily locked. Try again later.")

        if not verify_password(password, user.password_hash):
            # Persist the failure counter in its own committed step so the
            # attempted lock is not rolled back by the raised AuthError.
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_max_attempts:
                user.locked_until = now + timedelta(seconds=settings.login_lockout_seconds)
                user.failed_login_count = 0
                log.warning("account_locked", user_id=str(user.id))
            await self._commit_side_effect()
            raise AuthError("Invalid credentials")

        if not user.is_active:
            raise AuthError("Account is disabled")

        # Successful login: reset counters, maybe rehash.
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        token = await self._issue_session(user, user_agent=user_agent, ip_address=ip_address)
        log.info("user_login", user_id=str(user.id))
        return user, token

    async def logout(self, token: str) -> None:
        token_hash = hash_session_token(token, settings.session_secret)
        session = await self.sessions.get_by_token_hash(token_hash)
        if session is not None:
            await self.sessions.revoke(session)

    async def logout_all(self, user_id: uuid.UUID) -> None:
        await self.sessions.revoke_all_for_user(user_id)

    async def list_sessions(self, user_id: uuid.UUID) -> list[SessionModel]:
        return await self.sessions.list_for_user(user_id)

    async def revoke_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        session = await self.session.get(SessionModel, session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundError("Session not found")
        await self.sessions.revoke(session)

    async def request_password_reset(self, email: str) -> str | None:
        user = await self.users.get_by_email(email)
        if user is None:
            # Do not reveal whether the email exists.
            return None
        raw = secrets.token_urlsafe(32)
        token_hash = hash_session_token(raw, settings.session_secret)
        self.session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await self.session.flush()
        return raw

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        token_hash = hash_session_token(raw_token, settings.session_secret)
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(UTC),
        )
        token = (await self.session.execute(stmt)).scalar_one_or_none()
        if token is None:
            raise ValidationError("Invalid or expired reset token")
        user = await self.session.get(User, token.user_id)
        if user is None:
            raise NotFoundError("User not found")
        user.password_hash = hash_password(new_password)
        token.used_at = datetime.now(UTC)
        await self.sessions.revoke_all_for_user(user.id)
        await self.session.flush()

    async def _issue_session(
        self, user: User, *, user_agent: str | None, ip_address: str | None
    ) -> str:
        token = generate_session_token()
        token_hash = hash_session_token(token, settings.session_secret)
        expires_at = datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)
        await self.sessions.create(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=(user_agent or "")[:512] or None,
            ip_address=ip_address,
        )
        return token

    async def _commit_side_effect(self) -> None:
        """Commit auth side-effects (e.g. lockout counter) independent of the
        caller's transaction, so they survive an AuthError being raised."""
        if self.session.in_transaction():
            await self.session.commit()
