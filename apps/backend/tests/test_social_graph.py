"""Follow graph and following feed filter (COMM-06)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student", name="Follow User"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name=name)


async def test_follow_and_unfollow_are_idempotent(client):
    a = await _register(client, "fl_a@ex.com")
    await client.post("/api/v1/auth/logout")
    await _register(client, "fl_b@ex.com")

    # b follows a.
    r = await client.post(f"/api/v1/users/{a['id']}/follow")
    assert r.status_code == 200, r.text
    assert r.json()["is_following"] is True
    assert r.json()["followers"] == 1

    # Idempotent: follow again does not double-count.
    r2 = await client.post(f"/api/v1/users/{a['id']}/follow")
    assert r2.json()["followers"] == 1

    # Unfollow.
    r3 = await client.delete(f"/api/v1/users/{a['id']}/follow")
    assert r3.status_code == 200
    assert r3.json()["is_following"] is False
    assert r3.json()["followers"] == 0


async def test_cannot_follow_yourself(client):
    me = await _register(client, "fl_self@ex.com")
    r = await client.post(f"/api/v1/users/{me['id']}/follow")
    assert r.status_code == 409, r.text


async def test_follow_notifies_the_followee_properly(client):
    target = await _register(client, "fl_target2@ex.com", name="Target Dua")
    await client.post("/api/v1/auth/logout")
    await _register(client, "fl_follower2@ex.com", name="Follower Dua")
    await client.post(f"/api/v1/users/{target['id']}/follow")
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login", json={"email": "fl_target2@ex.com", "password": "Password123!"}
    )
    notifs = await client.get("/api/v1/notifications?limit=50")
    body = notifs.json() if isinstance(notifs.json(), list) else notifs.json().get("items", [])
    assert any("mengikuti Anda" in n["title"] for n in body)


async def test_following_feed_filter_shows_only_followed_authors(client):
    alice = await _register(client, "fl_alice@ex.com", name="Alice")
    await client.post("/api/v1/community/posts", json={"body": "pos alice", "topic": "filt"})
    await client.post("/api/v1/auth/logout")

    bob = await _register(client, "fl_bob@ex.com", name="Bob")
    await client.post("/api/v1/community/posts", json={"body": "pos bob", "topic": "filt"})
    await client.post("/api/v1/auth/logout")

    await _register(client, "fl_carol@ex.com", name="Carol")
    # Carol follows Alice only.
    await client.post(f"/api/v1/users/{alice['id']}/follow")

    feed = await client.get("/api/v1/community/posts?following=true&topic=filt")
    authors = {p["author_id"] for p in feed.json()}
    assert alice["id"] in authors
    assert bob["id"] not in authors


async def test_my_following_lists_followed_ids(client):
    a = await _register(client, "fl_x@ex.com")
    await client.post("/api/v1/auth/logout")
    await _register(client, "fl_y@ex.com")
    await client.post(f"/api/v1/users/{a['id']}/follow")
    r = await client.get("/api/v1/me/following")
    assert r.status_code == 200
    assert a["id"] in r.json()
