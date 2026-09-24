"""Roadmap task checkoff and editable progress tests (CARE-05)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Roadmap User")


async def _roadmap_with_tasks(client) -> dict:
    r = await client.post(
        "/api/v1/career/roadmap",
        json={
            "title": "Milestone Uji",
            "description": "desc",
            "period": "Jan 2026",
            "tasks": ["Tugas A", "Tugas B", "Tugas C", "Tugas D"],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_checking_task_derives_progress(client):
    """Progress is the fraction of done tasks, not a hardcoded step."""
    await _register(client, "roadmap_check@ex.com")
    m = await _roadmap_with_tasks(client)
    mid = m["id"]

    # Toggle one of four tasks -> 25%.
    r = await client.post(f"/api/v1/career/roadmap/{mid}/tasks/0/toggle")
    assert r.status_code == 200, r.text
    assert r.json()["progress_percent"] == 25
    assert r.json()["status"] == "in_progress"

    # Toggle it back -> 0%.
    r = await client.post(f"/api/v1/career/roadmap/{mid}/tasks/0/toggle")
    assert r.json()["progress_percent"] == 0

    # Complete all four -> 100% (and completed).
    for i in range(4):
        r = await client.post(f"/api/v1/career/roadmap/{mid}/tasks/{i}/toggle")
    assert r.json()["progress_percent"] == 100
    assert r.json()["status"] == "completed"


async def test_task_index_out_of_range_is_404(client):
    await _register(client, "roadmap_oob@ex.com")
    m = await _roadmap_with_tasks(client)
    r = await client.post(f"/api/v1/career/roadmap/{m['id']}/tasks/99/toggle")
    assert r.status_code == 404


async def test_milestone_completion_rewards_opt_idempotently(client):
    await _register(client, "roadmap_reward@ex.com")
    m = await _roadmap_with_tasks(client)
    mid = m["id"]
    for i in range(4):
        await client.post(f"/api/v1/career/roadmap/{mid}/tasks/{i}/toggle")

    # Re-completing (toggling off and on again) must not double-pay.
    await client.post(f"/api/v1/career/roadmap/{mid}/tasks/0/toggle")
    await client.post(f"/api/v1/career/roadmap/{mid}/tasks/0/toggle")

    import uuid as _uuid

    from sqlalchemy import select

    from app.models.identity import User
    from app.models.wallet import WalletLedgerEntry
    from app.services.keys import milestone_reward_key

    sm = client._sm  # type: ignore[attr-defined]
    async with sm() as s:
        me = (
            await s.execute(select(User).where(User.email == "roadmap_reward@ex.com"))
        ).scalar_one()
        ledger = (
            await s.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == "milestone",
                    WalletLedgerEntry.reference_id == mid,
                )
            )
        ).scalars().all()
    assert len(ledger) == 1, "milestone reward must be idempotent (one ledger entry)"
    assert ledger[0].amount == 20
    assert ledger[0].reward_key == milestone_reward_key(me.id, _uuid.UUID(mid))


async def test_reorder_rewrites_positions_atomically(client):
    await _register(client, "roadmap_reorder@ex.com")
    a = (await _roadmap_with_tasks(client))["id"]
    b = (await _roadmap_with_tasks(client))["id"]
    r = await client.post("/api/v1/career/roadmap/reorder", json={"ordered_ids": [b, a]})
    assert r.status_code == 200, r.text
    positions = [m["id"] for m in r.json()]
    assert positions == [b, a]

    # Reorder must reject an incomplete id set.
    bad = await client.post("/api/v1/career/roadmap/reorder", json={"ordered_ids": [a]})
    assert bad.status_code in (409, 422), bad.text


async def test_milestone_crud_is_owner_scoped(client):
    await _register(client, "roadmap_owner_a@ex.com")
    m = await _roadmap_with_tasks(client)
    mid = m["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "roadmap_owner_b@ex.com")
    assert (await client.post(f"/api/v1/career/roadmap/{mid}/tasks/0/toggle")).status_code == 404
    assert (await client.delete(f"/api/v1/career/roadmap/{mid}")).status_code == 404
