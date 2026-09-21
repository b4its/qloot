"""User / role / session repositories."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Role, User, UserRole
from app.models.identity import Session as SessionModel


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return (
            await self.session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()

    async def get_with_roles(self, user_id: uuid.UUID) -> User | None:
        from sqlalchemy.orm import selectinload

        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == user_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func_lower_email(email))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def assign_role(self, user: User, role_name: str) -> None:
        role = (
            await self.session.execute(select(Role).where(Role.name == role_name))
        ).scalar_one_or_none()
        if role is None:
            raise ValueError(f"Role {role_name} not found")
        exists = (
            await self.session.execute(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
            )
        ).scalar_one_or_none()
        if exists is None:
            self.session.add(UserRole(user_id=user.id, role_id=role.id))
            await self.session.flush()

    async def set_role(self, user: User, role_name: str) -> None:
        """Replace all of a user's roles with a single role."""
        await self.session.execute(delete(UserRole).where(UserRole.user_id == user.id))
        await self.session.flush()
        await self.assign_role(user, role_name)
        await self.session.refresh(user)


class SessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> SessionModel:
        obj = SessionModel(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_by_token_hash(self, token_hash: str) -> SessionModel | None:
        stmt = select(SessionModel).where(SessionModel.token_hash == token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[SessionModel]:
        stmt = (
            select(SessionModel)
            .where(SessionModel.user_id == user_id)
            .where(SessionModel.revoked_at.is_(None))
            .order_by(SessionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def revoke(self, session_obj: SessionModel) -> None:
        session_obj.revoked_at = datetime.now(UTC)
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        stmt = select(SessionModel).where(
            SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None)
        )
        for s in (await self.session.execute(stmt)).scalars().all():
            s.revoked_at = datetime.now(UTC)
        await self.session.flush()


def func_lower_email(email: str):
    from sqlalchemy import func

    return func.lower(User.email) == email.lower()
