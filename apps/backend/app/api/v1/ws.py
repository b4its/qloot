"""WebSocket endpoints for live rooms."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_session_token
from app.db.base import utcnow
from app.db.session import get_sessionmaker
from app.models.identity import Session as SessionModel
from app.models.identity import User
from app.models.room import Room
from app.services.realtime import event_bus, room_channel

router = APIRouter()
log = get_logger("ws")


async def _authenticate(token: str | None) -> User | None:
    if not token:
        return None
    token_hash = hash_session_token(token, settings.session_secret)
    sm = get_sessionmaker()
    async with sm() as db:
        session = (
            await db.execute(select(SessionModel).where(SessionModel.token_hash == token_hash))
        ).scalar_one_or_none()
        # A live socket must honour the same session lifetime as HTTP: reject
        # revoked *or expired* sessions, otherwise a stale token authenticates
        # the room stream indefinitely.
        if session is None or session.revoked_at is not None or session.expires_at <= utcnow():
            return None
        return (
            await db.execute(select(User).where(User.id == session.user_id))
        ).scalar_one_or_none()


@router.websocket("/ws/rooms/{room_id}")
async def room_ws(websocket: WebSocket, room_id: uuid.UUID) -> None:
    token = websocket.cookies.get(settings.session_cookie_name) or websocket.query_params.get(
        "token"
    )
    user = await _authenticate(token)
    if user is None:
        await websocket.close(code=4401)
        return

    sm = get_sessionmaker()
    async with sm() as db:
        room = (await db.execute(select(Room).where(Room.id == room_id))).scalar_one_or_none()
        if room is None:
            await websocket.close(code=4404)
            return
        # Enforce the same read visibility as the HTTP endpoints: a private room
        # is only streamable by its owner, members or an admin. Close with 4403
        # (forbidden) so a non-member cannot subscribe to a hidden room's events.
        from app.services.room_service import RoomService

        if not (
            user.has_role("admin")
            or room.owner_id == user.id
            or room.is_public
            or await RoomService(db).is_member(room_id, user.id)
        ):
            await websocket.close(code=4403)
            return

    await websocket.accept()
    channel = room_channel(str(room_id))
    presence_key = f"{room_id}:{user.id}"
    live_sockets = await event_bus.incr_connection(presence_key)
    if live_sockets == 1:
        # First socket for this user in this room: flip is_present on and
        # tell everyone else. A second tab from the same user is already
        # "present" — no duplicate event, no duplicate DB write.
        async with sm() as db:
            from app.services.room_service import RoomService

            await RoomService(db).mark_present(room_id, user.id)
            await db.commit()
        await event_bus.publish(channel, {"type": "presence.join", "user_id": str(user.id)})
    log.info("ws_connected", room_id=str(room_id), user_id=str(user.id), sockets=live_sockets)

    async def pump_events() -> None:
        async for message in event_bus.subscribe(channel):
            await websocket.send_json(message)

    pump_task = asyncio.create_task(pump_events())
    try:
        while True:
            # Client heartbeats / ephemeral signals.
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") in ("signal", "chat"):
                data["user_id"] = str(user.id)
                await event_bus.publish(channel, data)
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        # Await the cancelled task so its exception (if any) is retrieved and
        # the subscriber is released instead of leaking as a pending task.
        try:
            await pump_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 - best-effort cleanup
            pass
        remaining = await event_bus.decr_connection(presence_key)
        if remaining == 0:
            # Last socket for this user in this room closed: flip is_present
            # off (covers a browser tab close, not just an explicit "leave").
            async with sm() as db:
                from app.services.room_service import RoomService

                await RoomService(db).mark_absent(room_id, user.id)
                await db.commit()
            await event_bus.publish(channel, {"type": "presence.leave", "user_id": str(user.id)})
        log.info("ws_disconnected", room_id=str(room_id), user_id=str(user.id), sockets=remaining)
