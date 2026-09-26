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


async def test_my_task_completions_and_filters(client):
    await _register(client, "filter_task_owner@ex.com", "teacher")
    t1 = await client.post(
        "/api/v1/tasks",
        json={"title": "Membaca Dokumentasi", "kind": "learning", "reward_amount": 15},
    )
    assert t1.status_code == 201
    t1_id = t1.json()["id"]

    t2 = await client.post(
        "/api/v1/tasks",
        json={"title": "Latihan Harian Algoritma", "kind": "daily", "reward_amount": 10},
    )
    assert t2.status_code == 201
    t2_id = t2.json()["id"]

    # Filter tasks by q
    res_q = await client.get("/api/v1/tasks?q=Dokumentasi")
    assert res_q.status_code == 200
    assert any(t["id"] == t1_id for t in res_q.json())
    assert not any(t["id"] == t2_id for t in res_q.json())

    # Filter tasks by kind
    res_kind = await client.get("/api/v1/tasks?kind=learning")
    assert res_kind.status_code == 200
    assert any(t["id"] == t1_id for t in res_kind.json())
    assert all(t["kind"] == "learning" for t in res_kind.json())

    # Switch to student and complete t1
    await client.post("/api/v1/auth/logout")
    await _register(client, "student_completions@ex.com", "student")

    initial_comp = await client.get("/api/v1/tasks/me/completions")
    assert initial_comp.status_code == 200
    assert not any(c["task_id"] == t1_id for c in initial_comp.json())

    # Complete task
    c_res = await client.post(f"/api/v1/tasks/{t1_id}/complete")
    assert c_res.status_code == 200

    # Retrieve completions
    after_comp = await client.get("/api/v1/tasks/me/completions")
    assert after_comp.status_code == 200
    assert any(c["task_id"] == t1_id for c in after_comp.json())


async def test_teacher_sees_own_inactive_and_scheduled_tasks_student_does_not(client):
    """A teacher's management list must include drafts (inactive) and future
    (scheduled) tasks — otherwise they vanish from the very panel used to
    publish and edit them. Learners must never see them.
    """
    await _register(client, "mgmt_teacher@ex.com", "teacher")
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()

    draft = await client.post(
        "/api/v1/tasks",
        json={"title": "Draft Tugas", "kind": "daily", "reward_amount": 5},
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]
    # Deactivate it — the panel's "Nonaktifkan" action.
    deactivated = await client.patch(f"/api/v1/tasks/{draft_id}", json={"is_active": False})
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    scheduled = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Terjadwal Tugas",
            "kind": "weekly",
            "reward_amount": 8,
            "starts_at": future,
        },
    )
    assert scheduled.status_code == 201, scheduled.text
    scheduled_id = scheduled.json()["id"]

    live = await client.post(
        "/api/v1/tasks",
        json={"title": "Live Tugas", "kind": "daily", "reward_amount": 3},
    )
    assert live.status_code == 201, live.text
    live_id = live.json()["id"]

    # Teacher's management view: all three are visible.
    mgmt = await client.get("/api/v1/tasks")
    assert mgmt.status_code == 200
    ids = {t["id"] for t in mgmt.json()}
    assert {draft_id, scheduled_id, live_id} <= ids

    # status filter narrows correctly.
    inactive = await client.get("/api/v1/tasks?status=inactive")
    inactive_ids = {t["id"] for t in inactive.json()}
    assert draft_id in inactive_ids and live_id not in inactive_ids

    scheduled_only = await client.get("/api/v1/tasks?status=scheduled")
    scheduled_ids = {t["id"] for t in scheduled_only.json()}
    assert scheduled_id in scheduled_ids and live_id not in scheduled_ids

    available_only = await client.get("/api/v1/tasks?status=available")
    available_ids = {t["id"] for t in available_only.json()}
    assert live_id in available_ids
    assert draft_id not in available_ids and scheduled_id not in available_ids

    # Learner view: only the live task is listed.
    await client.post("/api/v1/auth/logout")
    await _register(client, "mgmt_student@ex.com", "student")
    learner = await client.get("/api/v1/tasks")
    learner_ids = {t["id"] for t in learner.json()}
    assert live_id in learner_ids
    assert draft_id not in learner_ids and scheduled_id not in learner_ids


async def test_teacher_does_not_see_another_teachers_tasks(client):
    await _register(client, "owner_a@ex.com", "teacher")
    a_task = await client.post(
        "/api/v1/tasks", json={"title": "Milik A", "kind": "daily", "reward_amount": 4}
    )
    a_id = a_task.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "owner_b@ex.com", "teacher")
    b_list = await client.get("/api/v1/tasks")
    assert all(t["id"] != a_id for t in b_list.json())


async def test_task_update_can_clear_schedule_and_rejects_bad_window(client):
    await _register(client, "sched_owner@ex.com", "teacher")
    start = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    end = (datetime.now(UTC) + timedelta(hours=3)).isoformat()

    created = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Scheduled",
            "kind": "daily",
            "reward_amount": 5,
            "starts_at": start,
            "ends_at": end,
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    # Clearing the schedule with explicit null must persist.
    cleared = await client.patch(
        f"/api/v1/tasks/{task_id}", json={"starts_at": None, "ends_at": None}
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["starts_at"] is None
    assert cleared.json()["ends_at"] is None

    # An inverted window on create is rejected.
    bad = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Bad window",
            "kind": "daily",
            "reward_amount": 5,
            "starts_at": end,
            "ends_at": start,
        },
    )
    assert bad.status_code == 422
