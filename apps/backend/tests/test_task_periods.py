"""Task window + recurring-period behaviour (daily/weekly resets)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services.keys import task_reward_key

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Task User")


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


def test_daily_period_key_uses_platform_timezone_not_utc_midnight():
    """A moment just after UTC midnight is still 'yesterday evening' in WIB.

    GAME-03: daily tasks must reset at local (Asia/Jakarta) midnight, not at
    07:00 WIB (UTC midnight). 2026-09-20T01:00:00Z is 2026-09-20T08:00 WIB —
    but 2026-09-19T18:00:00Z (still 2026-09-19 UTC) is already 2026-09-20T01:00
    WIB, i.e. the *next* WIB day.
    """
    from app.api.v1.tasks import _period_key

    just_before_utc_midnight = datetime(2026, 9, 19, 18, 0, 0, tzinfo=UTC)
    # In WIB (UTC+7) this is already the next calendar day.
    assert _period_key("daily", just_before_utc_midnight) == "2026-09-20"

    just_after_utc_midnight = datetime(2026, 9, 19, 23, 0, 0, tzinfo=UTC)
    assert _period_key("daily", just_after_utc_midnight) == "2026-09-20"


def test_weekly_period_key_rolls_over_across_iso_years():
    """ISO week numbering can cross a Gregorian year boundary; verify the
    'weekly' bucket follows ISO week/year (not calendar year) and does so in
    the platform timezone.
    """
    from app.api.v1.tasks import _period_key

    # 2026-01-01 is a Thursday -> ISO week 1 of 2026.
    start_of_iso_2026 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert _period_key("weekly", start_of_iso_2026) == "2026-W01"

    # 2025-12-29 (Monday) is ISO week 1 of 2026 (last days of Dec can belong to
    # the following ISO year).
    late_dec = datetime(2025, 12, 29, 12, 0, 0, tzinfo=UTC)
    assert _period_key("weekly", late_dec) == "2026-W01"

    # A week later must be a different bucket.
    a_week_later = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
    assert _period_key("weekly", a_week_later) == "2026-W02"


async def test_daily_task_reset_boundary_is_wib_midnight(client, monkeypatch):
    """End-to-end: completing a daily task twice on the same WIB calendar day
    (even though the two calls straddle UTC midnight) is rejected; completing
    it again after the WIB day rolls over is accepted.
    """
    import app.api.v1.tasks as tasks_module

    await _register(client, "task_owner3@ex.com", "teacher")
    created = await client.post(
        "/api/v1/tasks", json={"title": "WIB daily", "kind": "daily", "reward_amount": 5}
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "task_student3@ex.com", "student")

    def _frozen_now_factory(instant: datetime):
        class _Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant

        return _Frozen

    # 2026-09-19T23:00:00Z == 2026-09-20T06:00 WIB.
    monkeypatch.setattr(
        tasks_module, "datetime", _frozen_now_factory(datetime(2026, 9, 19, 23, 0, 0, tzinfo=UTC))
    )
    first = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert first.status_code == 200, first.text

    # 2026-09-20T00:30:00Z == 2026-09-20T07:30 WIB — same WIB calendar day.
    monkeypatch.setattr(
        tasks_module, "datetime", _frozen_now_factory(datetime(2026, 9, 20, 0, 30, 0, tzinfo=UTC))
    )
    again = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert again.status_code == 409

    # 2026-09-20T17:30:00Z == 2026-09-21T00:30 WIB — next WIB calendar day.
    monkeypatch.setattr(
        tasks_module, "datetime", _frozen_now_factory(datetime(2026, 9, 20, 17, 30, 0, tzinfo=UTC))
    )
    next_day = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert next_day.status_code == 200, next_day.text
