"""Community reporting and admin moderation tests (COMM-01)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Mod User")


async def _make_post(client, body="Pos untuk dimoderasi") -> str:
    r = await client.post("/api/v1/community/posts", json={"body": body, "topic": "Umum"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_user_can_report_a_post_once(client):
    await _register(client, "mod_author1@ex.com")
    post_id = await _make_post(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "mod_reporter1@ex.com")
    r = await client.post(
        "/api/v1/community/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "Spam"},
    )
    assert r.status_code == 201, r.text
    # Second report of the same target -> 409.
    dup = await client.post(
        "/api/v1/community/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "Spam lagi"},
    )
    assert dup.status_code == 409, dup.text


async def test_admin_can_hide_a_reported_post_and_it_leaves_feed_but_not_author(client):
    await _register(client, "mod_author2@ex.com")
    post_id = await _make_post(client, body="Pos yang akan disembunyikan")
    await client.post("/api/v1/auth/logout")

    await _register(client, "mod_reporter2@ex.com")
    rep = await client.post(
        "/api/v1/community/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "Tidak pantas"},
    )
    report_id = rep.json()["id"]
    await client.post("/api/v1/auth/logout")

    # Admin hides it.
    await _register(client, "mod_admin2@ex.com", "admin")
    queue = await client.get("/api/v1/community/reports?status_filter=open")
    assert queue.status_code == 200, queue.text
    assert any(r["id"] == report_id for r in queue.json())

    hidden = await client.post(
        f"/api/v1/community/reports/{report_id}/moderate",
        json={"action": "hide", "reason": "Melanggar aturan"},
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["status"] == "actioned"

    # Hidden post is gone from the feed for others.
    await client.post("/api/v1/auth/logout")
    await _register(client, "mod_bystander2@ex.com")
    feed = await client.get("/api/v1/community/posts")
    assert all(p["id"] != post_id for p in feed.json())

    # ...but still visible to its author.
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login",
        json={"email": "mod_author2@ex.com", "password": "Password123!"},
    )
    own_feed = await client.get("/api/v1/community/posts")
    assert any(p["id"] == post_id and p["hidden"] for p in own_feed.json())


async def test_admin_can_dismiss_a_report(client):
    await _register(client, "mod_author3@ex.com")
    post_id = await _make_post(client)
    await client.post("/api/v1/auth/logout")
    await _register(client, "mod_reporter3@ex.com")
    report_id = (
        await client.post(
            "/api/v1/community/reports",
            json={"target_type": "post", "target_id": post_id, "reason": "Coba"},
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "mod_admin3@ex.com", "admin")
    out = await client.post(
        f"/api/v1/community/reports/{report_id}/moderate", json={"action": "dismiss"}
    )
    assert out.status_code == 200, out.text
    assert out.json()["status"] == "dismissed"

    # Post remains visible.
    feed = await client.get("/api/v1/community/posts")
    assert any(p["id"] == post_id for p in feed.json())


async def test_students_cannot_access_moderation_queue(client):
    await _register(client, "mod_student4@ex.com")
    r = await client.get("/api/v1/community/reports")
    assert r.status_code == 403, r.text


async def test_moderation_is_audited(client):
    await _register(client, "mod_author5@ex.com")
    post_id = await _make_post(client)
    await client.post("/api/v1/auth/logout")
    await _register(client, "mod_reporter5@ex.com")
    report_id = (
        await client.post(
            "/api/v1/community/reports",
            json={"target_type": "post", "target_id": post_id, "reason": "Audit"},
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "mod_admin5@ex.com", "admin")
    await client.post(
        f"/api/v1/community/reports/{report_id}/moderate", json={"action": "hide"}
    )

    from sqlalchemy import select

    from app.models.identity import AuditLog

    sm = client._sm  # type: ignore[attr-defined]
    async with sm() as s:
        row = (
            await s.execute(
                select(AuditLog).where(
                    AuditLog.action == "community.hide",
                    AuditLog.entity_id == report_id,
                )
            )
        ).scalar_one_or_none()
    assert row is not None
    assert row.request_id
