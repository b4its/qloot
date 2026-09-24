"""Room locked state: freezes new joins while status stays "open" (GAME-08).

The dead WS "chat" branch (frames echoed but never persisted/rendered) was
removed in the same commit — covered indirectly by test_room_ws.py's ping/
signal coverage still passing unchanged.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Room Lock User")


async def test_lock_blocks_new_joins_but_not_existing_members(client):
    await _register(client, "lock_owner@ex.com", "teacher")
    room = await client.post("/api/v1/rooms", json={"name": "Lockable", "is_public": True})
    assert room.status_code == 201, room.text
    room_id = room.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/open")

    await client.post("/api/v1/auth/logout")
    await _register(client, "lock_early@ex.com", "student")
    early_join = await client.post(f"/api/v1/rooms/{room_id}/join")
    assert early_join.status_code == 200, early_join.text

    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login", json={"email": "lock_owner@ex.com", "password": "Password123!"}
    )
    locked = await client.post(f"/api/v1/rooms/{room_id}/lock")
    assert locked.status_code == 200, locked.text
    assert locked.json()["is_locked"] is True

    # A brand-new joiner is rejected once locked.
    await client.post("/api/v1/auth/logout")
    await _register(client, "lock_late@ex.com", "student")
    late_join = await client.post(f"/api/v1/rooms/{room_id}/join")
    assert late_join.status_code == 409, late_join.text

    # The early joiner re-joining (already a member) is unaffected by the lock.
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login", json={"email": "lock_early@ex.com", "password": "Password123!"}
    )
    rejoin = await client.post(f"/api/v1/rooms/{room_id}/join")
    assert rejoin.status_code == 200, rejoin.text


async def test_unlock_restores_new_joins(client):
    await _register(client, "unlock_owner@ex.com", "teacher")
    room = await client.post("/api/v1/rooms", json={"name": "Unlockable", "is_public": True})
    room_id = room.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/open")
    await client.post(f"/api/v1/rooms/{room_id}/lock")
    unlocked = await client.post(f"/api/v1/rooms/{room_id}/unlock")
    assert unlocked.status_code == 200, unlocked.text
    assert unlocked.json()["is_locked"] is False

    await client.post("/api/v1/auth/logout")
    await _register(client, "unlock_student@ex.com", "student")
    joined = await client.post(f"/api/v1/rooms/{room_id}/join")
    assert joined.status_code == 200, joined.text


async def test_only_the_owner_or_admin_can_lock(client):
    await _register(client, "lockperm_owner@ex.com", "teacher")
    room = await client.post("/api/v1/rooms", json={"name": "Perm Room", "is_public": True})
    room_id = room.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/open")

    await client.post("/api/v1/auth/logout")
    await _register(client, "lockperm_other@ex.com", "teacher")
    r = await client.post(f"/api/v1/rooms/{room_id}/lock")
    assert r.status_code == 403


async def test_cannot_lock_a_room_that_is_not_open(client):
    await _register(client, "lockdraft_owner@ex.com", "teacher")
    room = await client.post("/api/v1/rooms", json={"name": "Draft Room", "is_public": True})
    room_id = room.json()["id"]
    # Never opened -> still "draft".
    r = await client.post(f"/api/v1/rooms/{room_id}/lock")
    assert r.status_code == 409
