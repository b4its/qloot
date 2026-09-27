"""Notification inbox management: paging, filters, bulk read, and delete.

The notifications screen relies on the ``/notifications/page`` bundle (items +
counts) staying consistent with the plain list + delete endpoints, so these
tests pin both the happy paths and the ownership boundaries.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Notif User")


async def _seed_notifications(client, count: int = 3) -> None:
    """Create ``count`` notifications for the current user through the real
    service so the feed is populated without depending on unrelated flows."""
    sm = client._sm  # type: ignore[attr-defined]
    me = (await client.get("/api/v1/auth/me")).json()
    async with sm() as s:
        from app.services.social_service import NotificationService

        svc = NotificationService(s)
        for i in range(count):
            await svc.notify(
                user_id=uuid.UUID(me["id"]),
                kind="reward" if i % 2 == 0 else "quest",
                title=f"Kabar {i}",
                body=f"Badan pesan {i}",
            )
        await s.commit()


async def test_notifications_page_bundles_items_and_counts(client):
    await _register(client, "notif_page@ex.com")
    await _seed_notifications(client, 4)

    r = await client.get("/api/v1/notifications/page?limit=2")
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"items", "total", "unread", "kind_counts"} <= set(body)
    assert len(body["items"]) == 2  # page respects the limit
    # Registration seeds a "system" welcome notification, so the seeded kinds
    # are a subset: 1 system + 2 reward + 2 quest.
    assert body["total"] == 5
    assert body["unread"] == 5
    assert body["kind_counts"].get("reward") == 2
    assert body["kind_counts"].get("quest") == 2
    assert body["kind_counts"].get("system") == 1


async def test_notifications_page_filters_by_kind_and_search(client):
    await _register(client, "notif_filter@ex.com")
    await _seed_notifications(client, 4)

    by_kind = await client.get("/api/v1/notifications/page?kind=quest")
    assert by_kind.status_code == 200
    kinds = {n["kind"] for n in by_kind.json()["items"]}
    assert kinds == {"quest"}
    assert by_kind.json()["total"] == 2

    by_q = await client.get("/api/v1/notifications/page?q=badan pesan 1")
    assert by_q.status_code == 200
    assert [n["title"] for n in by_q.json()["items"]] == ["Kabar 1"]
    assert by_q.json()["total"] == 1


async def test_notifications_page_read_only_and_oldest_first(client):
    """The "Dibaca" tab must exclude unread items, and oldest_first must reorder
    the server page (not just the current client page)."""
    await _register(client, "notif_readonly@ex.com")
    await _seed_notifications(client, 3)
    items = (await client.get("/api/v1/notifications/page")).json()["items"]
    await client.post("/api/v1/notifications/read-batch", json={"ids": [items[0]["id"]]})

    read_only = await client.get("/api/v1/notifications/page?read_only=true")
    assert read_only.status_code == 200, read_only.text
    body = read_only.json()
    assert body["total"] == 1  # only the one we marked read
    assert body["items"][0]["id"] == items[0]["id"]

    # Newest-first is the default; oldest-first flips the ordering server-side.
    newest = (await client.get("/api/v1/notifications/page?limit=2")).json()["items"]
    oldest = (
        await client.get("/api/v1/notifications/page?limit=2&oldest_first=true")
    ).json()["items"]
    assert newest[0]["id"] != oldest[0]["id"]
    assert newest[0]["created_at"] >= newest[1]["created_at"]
    assert oldest[0]["created_at"] <= oldest[1]["created_at"]


async def test_mark_read_batch_only_touches_owned_ids(client):
    await _register(client, "notif_batch@ex.com")
    await _seed_notifications(client, 3)
    items = (await client.get("/api/v1/notifications/page")).json()["items"]
    owned = [items[0]["id"], items[1]["id"]]

    r = await client.post("/api/v1/notifications/read-batch", json={"ids": owned})
    assert r.status_code == 200, r.text
    assert "2" in r.json()["message"]

    after = (await client.get("/api/v1/notifications/page")).json()
    assert after["unread"] == 2  # 4 total (1 welcome + 3) minus the 2 we read
    # A bogus id is a harmless no-op.
    again = await client.post(
        "/api/v1/notifications/read-batch", json={"ids": [str(uuid.uuid4())]}
    )
    assert again.status_code == 200
    assert "0" in again.json()["message"]


async def test_delete_notification_is_owner_scoped(client):
    await _register(client, "notif_owner@ex.com")
    await _seed_notifications(client, 2)
    mine = (await client.get("/api/v1/notifications/page")).json()["items"]

    # A different user cannot delete my notification.
    await client.post("/api/v1/auth/logout")
    await _register(client, "notif_other@ex.com")
    r = await client.delete(f"/api/v1/notifications/{mine[0]['id']}")
    assert r.status_code == 404, r.text

    # The owner can.
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login",
        json={"email": "notif_owner@ex.com", "password": "Password123!"},
    )
    r = await client.delete(f"/api/v1/notifications/{mine[0]['id']}")
    assert r.status_code == 200, r.text
    remaining = (await client.get("/api/v1/notifications/page")).json()
    assert remaining["total"] == 2  # 3 seeded (welcome + 2) minus the deleted one


async def test_clear_read_removes_only_read_notifications(client):
    await _register(client, "notif_clear@ex.com")
    await _seed_notifications(client, 3)
    items = (await client.get("/api/v1/notifications/page")).json()["items"]
    await client.post("/api/v1/notifications/read-batch", json={"ids": [items[0]["id"]]})

    r = await client.post("/api/v1/notifications/clear-read")
    assert r.status_code == 200, r.text
    assert "1" in r.json()["message"]

    after = (await client.get("/api/v1/notifications/page")).json()
    assert after["total"] == 3  # 4 seeded (welcome + 3) minus the 1 cleared
    assert after["unread"] == 3  # the three we never read survived
