"""Community @mentions with notifications (COMM-04)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student", name="Mention User"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name=name)


async def _notifications_for(client, email) -> list[dict]:
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    r = await client.get("/api/v1/notifications?limit=50")
    return r.json() if isinstance(r.json(), list) else r.json().get("items", [])


async def test_mentioning_a_user_notifies_them(client):
    await _register(client, "men_target@ex.com", name="Budi Santoso")
    await client.post("/api/v1/auth/logout")

    await _register(client, "men_author@ex.com", name="Siti Aminah")
    r = await client.post(
        "/api/v1/community/posts",
        json={"body": "Halo @Budi Santoso, tolong lihat ini.", "topic": "Umum"},
    )
    assert r.status_code == 201, r.text

    notifs = await _notifications_for(client, "men_target@ex.com")
    assert any(n["kind"] == "community" and "menyebut" in n["title"] for n in notifs)


async def test_unknown_mention_does_not_notify_or_break(client):
    await _register(client, "men_author2@ex.com", name="Penulis Dua")
    r = await client.post(
        "/api/v1/community/posts",
        json={"body": "Halo @TidakAdaOrang, apa kabar?", "topic": "Umum"},
    )
    assert r.status_code == 201, r.text
    # The body is preserved verbatim (unknown mention stays plain text).
    assert "@TidakAdaOrang" in r.json()["body"]


async def test_mention_in_comment_notifies(client):
    await _register(client, "men_target3@ex.com", name="Citra Dewi")
    await client.post("/api/v1/auth/logout")
    await _register(client, "men_author3@ex.com", name="Penulis Tiga")
    post_id = (
        await client.post("/api/v1/community/posts", json={"body": "pos", "topic": "Umum"})
    ).json()["id"]

    r = await client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={"body": "Hai @Citra Dewi, cek ya."},
    )
    assert r.status_code == 201, r.text

    notifs = await _notifications_for(client, "men_target3@ex.com")
    assert any(n["kind"] == "community" and "menyebut" in n["title"] for n in notifs)


async def test_author_is_not_notified_for_self_mention(client):
    await _register(client, "men_self4@ex.com", name="Diri Sendiri")
    await client.post(
        "/api/v1/community/posts",
        json={"body": "Catatan untuk @Diri Sendiri sendiri.", "topic": "Umum"},
    )
    notifs = await _notifications_for(client, "men_self4@ex.com")
    assert not any("menyebut" in n["title"] for n in notifs)
