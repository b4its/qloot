"""Room endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, TeacherUser
from app.db.session import transaction
from app.schemas.common import Message
from app.schemas.room import (
    InviteCreate,
    InviteOut,
    JoinByCode,
    LiveEntry,
    RoomCreate,
    RoomEventOut,
    RoomMemberOut,
    RoomOut,
    RoomUpdate,
)
from app.services.realtime import event_bus, room_channel
from app.services.room_service import RoomService

router = APIRouter()


@router.get("", response_model=list[RoomOut])
async def list_rooms(user: CurrentUser, db: DbSession, limit: int = 50, offset: int = 0):
    return await RoomService(db).list_all(user, limit=limit, offset=offset)


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await RoomService(db).create(user, **payload.model_dump())


@router.get("/{room_id}", response_model=RoomOut)
async def get_room(room_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await RoomService(db).get(room_id)


@router.patch("/{room_id}", response_model=RoomOut)
async def update_room(room_id: uuid.UUID, payload: RoomUpdate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await RoomService(db).update(room_id, user, **payload.model_dump(exclude_unset=True))


@router.post("/{room_id}/join", response_model=RoomMemberOut)
async def join_room(room_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        member = await RoomService(db).join(room_id, user)
    await event_bus.publish(
        room_channel(str(room_id)), {"type": "room.join", "user_id": str(user.id)}
    )
    return RoomMemberOut.model_validate(member)


@router.post("/join-by-code", response_model=RoomOut)
async def join_by_code(payload: JoinByCode, user: CurrentUser, db: DbSession):
    async with transaction(db):
        service = RoomService(db)
        room = await service.get_by_code(payload.code)
        await service.join(room.id, user)
    await event_bus.publish(
        room_channel(str(room.id)), {"type": "room.join", "user_id": str(user.id)}
    )
    return RoomOut.model_validate(room)


@router.post("/{room_id}/leave", response_model=Message)
async def leave_room(room_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        await RoomService(db).leave(room_id, user)
    await event_bus.publish(
        room_channel(str(room_id)), {"type": "room.leave", "user_id": str(user.id)}
    )
    return Message(message="Left room")


@router.post("/{room_id}/open", response_model=RoomOut)
async def open_room(room_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        room = await RoomService(db).open(room_id, user)
    await event_bus.publish(
        room_channel(str(room_id)), {"type": "room.open", "status": room.status}
    )
    return RoomOut.model_validate(room)


@router.post("/{room_id}/close", response_model=RoomOut)
async def close_room(room_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        room = await RoomService(db).close(room_id, user)
    await event_bus.publish(
        room_channel(str(room_id)), {"type": "room.close", "status": room.status}
    )
    return RoomOut.model_validate(room)


@router.get("/{room_id}/participants", response_model=list[RoomMemberOut])
async def participants(room_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await RoomService(db).participants(room_id)


@router.get("/accept-invite", response_model=RoomMemberOut)
async def accept_invite(user: CurrentUser, db: DbSession, code: str):
    async with transaction(db):
        member = await RoomService(db).accept_invite(code, user)
    return RoomMemberOut.model_validate(member)


@router.get("/{room_id}/live", response_model=list[LiveEntry])
async def live_leaderboard(room_id: uuid.UUID, user: CurrentUser, db: DbSession):
    rows = await RoomService(db).live_leaderboard(room_id)
    return [LiveEntry(**r) for r in rows]


@router.get("/{room_id}/events", response_model=list[RoomEventOut])
async def room_events(room_id: uuid.UUID, user: CurrentUser, db: DbSession, limit: int = 50):
    return await RoomService(db).recent_events(room_id, limit=limit)


@router.post("/{room_id}/invite", response_model=InviteOut)
async def invite(room_id: uuid.UUID, payload: InviteCreate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        inv = await RoomService(db).invite(room_id, user, email=payload.email, note=payload.note)
    return InviteOut.model_validate(inv)
