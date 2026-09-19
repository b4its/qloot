"""Room service: rooms, members, events."""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.identity import User
from app.models.room import Room, RoomEvent, RoomMember


def generate_room_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class RoomService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, owner: User, **data) -> Room:
        code = generate_room_code()
        while (
            await self.session.execute(select(Room).where(Room.code == code))
        ).scalar_one_or_none():
            code = generate_room_code()
        room = Room(owner_id=owner.id, code=code, **data)
        self.session.add(room)
        await self.session.flush()
        self.session.add(RoomMember(room_id=room.id, user_id=owner.id, role="teacher"))
        await self.session.flush()
        return room

    async def get(self, room_id: uuid.UUID) -> Room:
        room = await self.session.get(Room, room_id)
        if room is None:
            raise NotFoundError("Room not found")
        return room

    async def get_by_code(self, code: str) -> Room:
        room = (
            await self.session.execute(select(Room).where(Room.code == code.upper()))
        ).scalar_one_or_none()
        if room is None:
            raise NotFoundError("Room not found")
        return room

    async def list_all(self, user: User, *, limit: int = 50, offset: int = 0) -> list[Room]:
        stmt = select(Room).order_by(Room.created_at.desc()).limit(limit).offset(offset)
        if not user.has_role("teacher", "admin"):
            stmt = stmt.where(Room.is_public.is_(True))
        else:
            stmt = stmt.where(Room.owner_id == user.id) if not user.has_role("admin") else stmt
        return list((await self.session.execute(stmt)).scalars().all())

    async def update(self, room_id: uuid.UUID, user: User, **data) -> Room:
        room = await self._owned(room_id, user)
        for k, v in data.items():
            if v is not None:
                setattr(room, k, v)
        await self.session.flush()
        return room

    async def open(self, room_id: uuid.UUID, user: User) -> Room:
        room = await self._owned(room_id, user)
        room.status = "open"
        room.opens_at = room.opens_at or datetime.now(UTC)
        await self._emit(room.id, "opened", {"by": str(user.id)})
        await self.session.flush()
        return room

    async def close(self, room_id: uuid.UUID, user: User) -> Room:
        room = await self._owned(room_id, user)
        room.status = "closed"
        room.closes_at = datetime.now(UTC)
        await self._emit(room.id, "closed", {"by": str(user.id)})
        await self.session.flush()
        return room

    async def join(self, room_id: uuid.UUID, user: User) -> RoomMember:
        room = await self.get(room_id)
        if room.status in ("closed", "archived"):
            raise ConflictError("Room is closed")
        stmt = select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.user_id == user.id
        )
        member = (await self.session.execute(stmt)).scalar_one_or_none()
        if member is None:
            count = len(await self.participants(room_id))
            if count >= room.max_participants:
                raise ConflictError("Room is full")
            member = RoomMember(room_id=room_id, user_id=user.id, role="student")
            self.session.add(member)
        else:
            member.is_present = True
            member.left_at = None
        await self._emit(room_id, "joined", {"user_id": str(user.id)})
        await self.session.flush()
        return member

    async def leave(self, room_id: uuid.UUID, user: User) -> None:
        stmt = select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.user_id == user.id
        )
        member = (await self.session.execute(stmt)).scalar_one_or_none()
        if member is not None:
            member.is_present = False
            member.left_at = datetime.now(UTC)
            await self._emit(room_id, "left", {"user_id": str(user.id)})
            await self.session.flush()

    async def participants(self, room_id: uuid.UUID) -> list[RoomMember]:
        stmt = select(RoomMember).where(RoomMember.room_id == room_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def _emit(self, room_id: uuid.UUID, event_type: str, payload: dict) -> None:
        self.session.add(RoomEvent(room_id=room_id, event_type=event_type, payload=payload))

    async def _owned(self, room_id: uuid.UUID, user: User) -> Room:
        room = await self.get(room_id)
        if not user.has_role("admin") and room.owner_id != user.id:
            raise ForbiddenError("You do not own this room")
        return room
