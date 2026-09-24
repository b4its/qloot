"""Community notifications on comments and likes (COMM-03)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Community User")


async def _make_post(client, topic="Umum") -> str:
    r = await client.post("/api/v1/community/posts", json={"body": "Halo dunia", "topic": topic})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _notifications_for(client, email) -> list[dict]:
    """Read the notifications of the given user by logging in as them."""
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    r = await client.get("/api/v1/notifications?limit=50")
    assert r.status_code == 200, r.text
    return r.json() if isinstance(r.json(), list) else r.json().get("items", [])


async def test_comment_notifies_the_author_not_the_commenter(client):
    await _register(client, "comm_author1@ex.com")
    post_id = await _make_post(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "comm_commenter1@ex.com")
    r = await client.post(
        f"/api/v1/community/posts/{post_id}/comments", json={"body": "Komentar pertama"}
    )
    assert r.status_code == 201, r.text

    # Author sees a notification.
    author_notifs = await _notifications_for(client, "comm_author1@ex.com")
    assert any(n["kind"] == "community" for n in author_notifs)

    # Commenter does NOT get notified for their own comment.
    commenter_notifs = await _notifications_for(client, "comm_commenter1@ex.com")
    assert not any(
        n["kind"] == "community" and "komentari pos Anda" in n["title"] for n in commenter_notifs
    )


async def test_like_notifies_the_author(client):
    await _register(client, "comm_author2@ex.com")
    post_id = await _make_post(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "comm_liker2@ex.com")
    r = await client.post(f"/api/v1/community/posts/{post_id}/like")
    assert r.status_code == 200, r.text

    notifs = await _notifications_for(client, "comm_author2@ex.com")
    assert any(n["kind"] == "community" and "menyukai" in n["title"] for n in notifs)


async def test_like_unlike_does_not_spam_notifications(client):
    await _register(client, "comm_author3@ex.com")
    post_id = await _make_post(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "comm_liker3@ex.com")
    await client.post(f"/api/v1/community/posts/{post_id}/like")
    # Unlike (toggle off) must not create a second notification.
    await client.post(f"/api/v1/community/posts/{post_id}/like")

    notifs = await _notifications_for(client, "comm_author3@ex.com")
    likes = [n for n in notifs if n["kind"] == "community" and "menyukai" in n["title"]]
    assert len(likes) == 1


async def test_muted_community_kind_suppresses_delivery(client):
    """Turning off the community kind suppresses new notifications (C54)."""
    await _register(client, "comm_author4@ex.com")
    post_id = await _make_post(client)
    # Mute community notifications.
    await client.put("/api/v1/notifications/preferences", json={"muted_kinds": ["community"]})
    await client.post("/api/v1/auth/logout")

    await _register(client, "comm_commenter4@ex.com")
    await client.post(
        f"/api/v1/community/posts/{post_id}/comments", json={"body": "hai"}
    )

    notifs = await _notifications_for(client, "comm_author4@ex.com")
    assert not any(n["kind"] == "community" for n in notifs)
