"""WebSocket room endpoint: auth, visibility, heartbeat, and presence
persistence (GAME-06 + supporting coverage).

Uses Starlette's synchronous ``TestClient.websocket_connect`` against the same
FastAPI ``app`` object the async ``client`` fixture already patched (dependency
overrides bind both to the same test database), and passes the session token
via the ``?token=`` query param the endpoint already supports for non-browser
clients.
"""

from __future__ import annotations

import warnings

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from app.main import app
from app.models.room import RoomMember

pytestmark = pytest.mark.integration


def _ws_client() -> TestClient:
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="starlette.testclient")
    return TestClient(app)


async def _register_and_token(client, email, role="student", **kw) -> str:
    from tests.helpers import register_actor

    await register_actor(client, email, role, **kw)
    # The session cookie value itself is the bearer token the WS endpoint
    # accepts via ?token=.
    cookie = client.cookies.get("qloot_session")
    assert cookie, "login must set the session cookie"
    return cookie


async def _create_open_room(client) -> str:
    r = await client.post("/api/v1/rooms", json={"name": "WS Room", "is_public": True})
    assert r.status_code == 201, r.text
    room_id = r.json()["id"]
    opened = await client.post(f"/api/v1/rooms/{room_id}/open")
    assert opened.status_code == 200, opened.text
    return room_id


async def test_ws_rejects_missing_token(client):
    await _register_and_token(client, "ws_notoken@ex.com", "teacher")
    room_id = await _create_open_room(client)
    with (
        _ws_client() as tc,
        pytest.raises(Exception) as exc_info,  # noqa: PT011
        tc.websocket_connect(f"/api/v1/ws/rooms/{room_id}"),
    ):
        pass
    # Starlette raises WebSocketDisconnect with the close code on reject.
    assert getattr(exc_info.value, "code", None) == 4401


async def test_ws_rejects_invalid_token(client):
    await _register_and_token(client, "ws_badtoken@ex.com", "teacher")
    room_id = await _create_open_room(client)
    with (
        _ws_client() as tc,
        pytest.raises(Exception) as exc_info,  # noqa: PT011
        tc.websocket_connect(f"/api/v1/ws/rooms/{room_id}?token=not-a-real-token"),
    ):
        pass
    assert getattr(exc_info.value, "code", None) == 4401


async def test_ws_ping_pong_and_presence_persisted(client, session):
    await _register_and_token(client, "ws_owner@ex.com", "teacher")
    room_id = await _create_open_room(client)

    await client.post("/api/v1/auth/logout")
    token = await _register_and_token(client, "ws_student@ex.com", "student")
    join = await client.post(f"/api/v1/rooms/{room_id}/join")
    assert join.status_code == 200, join.text
    me = (await client.get("/api/v1/auth/me")).json()["id"]

    with _ws_client() as tc, tc.websocket_connect(f"/api/v1/ws/rooms/{room_id}?token={token}") as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}

        # Presence must be persisted while the socket is open.
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(session.bind, expire_on_commit=False)
        async with sm() as fresh:
            member = (
                await fresh.execute(
                    select(RoomMember).where(
                        RoomMember.room_id == room_id, RoomMember.user_id == me
                    )
                )
            ).scalar_one()
            assert member.is_present is True


async def test_room_service_mark_present_and_mark_absent(session):
    """Unit-level coverage for the presence toggle the WS handler calls on
    connect/disconnect (GAME-06). The end-to-end socket lifecycle is covered
    by test_ws_ping_pong_and_presence_persisted for the connect side; Starlette's
    TestClient does not reliably surface server-side WebSocketDisconnect
    within a single test process, so the disconnect path is verified directly
    against the same RoomService methods ws.py calls in its `finally` block.
    """
    from app.services.room_service import RoomService

    owner = await _user(session, "ws_unit_owner@ex.com", "teacher")
    room = await RoomService(session).create(owner, name="Unit WS Room", is_public=True)
    student = await _user(session, "ws_unit_student@ex.com", "student")
    await RoomService(session).join(room.id, student)
    await session.commit()

    await RoomService(session).mark_present(room.id, student.id)
    await session.commit()
    member = (
        await session.execute(
            select(RoomMember).where(RoomMember.room_id == room.id, RoomMember.user_id == student.id)
        )
    ).scalar_one()
    assert member.is_present is True

    await RoomService(session).mark_absent(room.id, student.id)
    await session.commit()
    member = (
        await session.execute(
            select(RoomMember).where(RoomMember.room_id == room.id, RoomMember.user_id == student.id)
        )
    ).scalar_one()
    assert member.is_present is False
    assert member.left_at is not None


async def _user(session, email, role="student"):
    import uuid

    from sqlalchemy.orm import selectinload

    from app.core.security import hash_password
    from app.models.identity import Role, User, UserRole

    role_row = (await session.execute(select(Role).where(Role.name == role))).scalar_one()
    u = User(
        email=email,
        full_name="WS Unit User",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + (uuid.uuid4().hex + uuid.uuid4().hex)[:40],
    )
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role_row.id))
    await session.flush()
    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == u.id)
    )
    return (await session.execute(stmt)).scalar_one()


async def test_ws_second_tab_keeps_presence_while_one_socket_remains(client, session):
    """Two sockets for the same user in the same room: connecting both keeps
    presence on; the connection counter (EventBus.incr/decr_connection) is
    what ws.py uses to decide whether a disconnect is the *last* socket —
    verified directly here since TestClient's WebSocketDisconnect timing is
    unreliable within a single test process (see test above).
    """
    from app.services.realtime import event_bus

    await _register_and_token(client, "ws_owner2@ex.com", "teacher")
    room_id = await _create_open_room(client)

    await client.post("/api/v1/auth/logout")
    token = await _register_and_token(client, "ws_student2@ex.com", "student")
    await client.post(f"/api/v1/rooms/{room_id}/join")
    me = (await client.get("/api/v1/auth/me")).json()["id"]

    key = f"{room_id}:{me}"
    # Simulate two tabs connecting.
    assert await event_bus.incr_connection(key) == 1
    assert await event_bus.incr_connection(key) == 2
    # First tab closes: still one socket left -> presence must stay on.
    assert await event_bus.decr_connection(key) == 1
    # Second tab closes: now zero -> this is what triggers mark_absent in ws.py.
    assert await event_bus.decr_connection(key) == 0

    with _ws_client() as tc, tc.websocket_connect(f"/api/v1/ws/rooms/{room_id}?token={token}") as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(session.bind, expire_on_commit=False)
        async with sm() as fresh:
            member = (
                await fresh.execute(
                    select(RoomMember).where(RoomMember.room_id == room_id, RoomMember.user_id == me)
                )
            ).scalar_one()
            assert member.is_present is True


async def test_ws_rejects_non_member_of_private_room(client):
    await _register_and_token(client, "ws_owner3@ex.com", "teacher")
    r = await client.post("/api/v1/rooms", json={"name": "Private WS Room", "is_public": False})
    assert r.status_code == 201, r.text
    room_id = r.json()["id"]
    opened = await client.post(f"/api/v1/rooms/{room_id}/open")
    assert opened.status_code == 200, opened.text

    await client.post("/api/v1/auth/logout")
    token = await _register_and_token(client, "ws_outsider@ex.com", "student")
    # Never joined the private room.
    with (
        _ws_client() as tc,
        pytest.raises(Exception) as exc_info,  # noqa: PT011
        tc.websocket_connect(f"/api/v1/ws/rooms/{room_id}?token={token}"),
    ):
        pass
    assert getattr(exc_info.value, "code", None) == 4403
