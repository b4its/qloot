"""Task window + recurring-period behaviour (daily/weekly resets)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services.keys import task_reward_key

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Task User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_daily_task_can_be_completed_once_per_day(client):
    await _register(client, "task_owner@ex.com", "teacher")
    created = await client.post(
        "/api/v1/tasks", json={"title": "Daily login", "kind": "daily", "reward_amount": 10}
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "task_student@ex.com", "student")

    first = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert first.status_code == 200, first.text
    # Same period -> rejected.
    again = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert again.status_code == 409


async def test_task_reward_key_is_period_scoped():
    t = uuid.uuid4()
    u = uuid.uuid4()
    d1 = task_reward_key(t, u, "2026-09-19")
    d2 = task_reward_key(t, u, "2026-09-19")
    d3 = task_reward_key(t, u, "2026-09-20")
    assert d1 == d2
    assert d1 != d3


async def test_task_not_yet_started_cannot_be_completed(client):
    await _register(client, "task_owner2@ex.com", "teacher")
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    created = await client.post(
        "/api/v1/tasks",
        json={"title": "Future task", "kind": "daily", "reward_amount": 5, "starts_at": future},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "task_student2@ex.com", "student")

    r = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert r.status_code == 409
    # And it is not listed as currently available.
    listed = await client.get("/api/v1/tasks")
    assert all(t["id"] != task_id for t in listed.json())
