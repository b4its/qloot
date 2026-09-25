"""Tests for the social (notifications/badges) and new feature endpoints."""

from __future__ import annotations

import io

import pytest

from tests.pdf_util import make_pdf

pytestmark = pytest.mark.integration


async def _register(
    client, email, role="student", name="Test User", class_code=None, class_type=None
):
    from tests.helpers import register_actor

    return await register_actor(
        client,
        email,
        role,
        full_name=name,
        class_code=class_code,
        class_type=class_type,
    )


async def test_welcome_notification_on_register(client):
    await _register(client, "notif@ex.com")
    feed = await client.get("/api/v1/notifications")
    assert feed.status_code == 200
    items = feed.json()
    assert any(n["kind"] == "system" for n in items)
    count = await client.get("/api/v1/notifications/unread-count")
    assert count.json()["unread"] >= 1

    # Mark all read -> unread becomes 0.
    await client.post("/api/v1/notifications/read-all")
    count2 = await client.get("/api/v1/notifications/unread-count")
    assert count2.json()["unread"] == 0


async def test_admin_broadcast_notification(client):
    await _register(client, "broadcast_target@ex.com")
    await client.post("/api/v1/auth/logout")
    from tests.helpers import register_actor

    await register_actor(client, "admin_b@ex.com", "teacher")
    # Promote to admin directly via DB is covered elsewhere; broadcast requires admin.
    # Here we only assert a non-admin is rejected and the endpoint exists.
    resp = await client.post("/api/v1/admin/notifications", json={"title": "Hi", "body": "all"})
    assert resp.status_code == 403


async def test_badge_catalog_available(client):
    await _register(client, "badge@ex.com")
    catalog = await client.get("/api/v1/badges")
    assert catalog.status_code == 200
    assert len(catalog.json()) >= 1
    # Badges are off-chain gamification; the catalog exposes code/name/icon/points.
    assert all({"code", "name", "icon", "points", "rarity"} <= set(b) for b in catalog.json())
    assert all(b["rarity"] in ("common", "rare", "epic", "legendary") for b in catalog.json())


def test_rarity_for_points_is_deterministic():
    """GAME-13: points -> rarity mapping matches the migration's backfill."""
    from app.services.social_service import rarity_for_points

    assert rarity_for_points(0) == "common"
    assert rarity_for_points(19) == "common"
    assert rarity_for_points(20) == "rare"
    assert rarity_for_points(39) == "rare"
    assert rarity_for_points(40) == "epic"
    assert rarity_for_points(99) == "epic"
    assert rarity_for_points(100) == "legendary"
    assert rarity_for_points(1000) == "legendary"


async def test_catalog_rarity_matches_each_badges_points(client):
    await _register(client, "badge_rarity@ex.com")
    from app.services.social_service import rarity_for_points

    catalog = (await client.get("/api/v1/badges")).json()
    for b in catalog:
        assert b["rarity"] == rarity_for_points(b["points"])


async def test_perfect_exam_awards_badge(client):
    """A flawless graded attempt earns the 'perfect_exam' badge."""
    await _register(client, "badge_teacher@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "Perfect Exam"})
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Apa itu fotosintesis?",
            "correct_answer": "proses tumbuhan mengubah cahaya",
        },
    )
    qid = q.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "badge_student@ex.com", "student")
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = attempt.json()["id"]
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}",
        json={"answer_text": "proses tumbuhan mengubah cahaya"},
    )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    grade = await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})
    assert grade.status_code == 200, grade.text

    owned = await client.get("/api/v1/me/badges")
    assert owned.status_code == 200
    codes = {b["badge"]["code"] for b in owned.json()}
    assert "perfect_exam" in codes


async def test_material_summary_and_qa(client):
    await _register(client, "ai_teacher@ex.com", "teacher")
    pdf = make_pdf("Machine learning is a branch of artificial intelligence. It uses data.")
    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("m.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert up.status_code == 201, up.text
    mat_id = up.json()["id"]

    summary = await client.get(f"/api/v1/materials/{mat_id}/summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["summary"]

    ask = await client.post(
        f"/api/v1/materials/{mat_id}/ask",
        json={"question": "What is machine learning?", "language": "en"},
    )
    assert ask.status_code == 200, ask.text
    assert ask.json()["answer"]
    assert 0 <= ask.json()["confidence_bp"] <= 10000

    # The owner can list their materials.
    listing = await client.get("/api/v1/materials")
    assert listing.status_code == 200, listing.text
    assert any(m["id"] == mat_id for m in listing.json())


async def test_class_based_subject_access(client):
    """A student only sees subjects for their own class (+ broadcasts)."""
    # Teacher creates a 1A subject and a 2D subject.
    await _register(client, "t_class@ex.com", "teacher")
    a = await client.post(
        "/api/v1/courses",
        json={"title": "Kelas-A Sains", "class_code": "1A", "class_type": "IPA"},
    )
    assert a.status_code == 201, a.text
    b = await client.post(
        "/api/v1/courses",
        json={"title": "Kelas-D Sosial", "class_code": "2D", "class_type": "IPS"},
    )
    assert b.status_code == 201, b.text
    broadcast = await client.post(
        "/api/v1/courses",
        json={"title": "Broadcast Sekolah", "class_code": "UMUM"},
    )
    assert broadcast.status_code == 201, broadcast.text
    await client.post("/api/v1/auth/logout")

    # A 1A student sees the 1A subject + the broadcast, never the 2D subject.
    await _register(client, "s_1a@ex.com", class_code="1A", class_type="IPA")
    subs = await client.get("/api/v1/courses")
    titles = {s["title"] for s in subs.json()}
    assert "Kelas-A Sains" in titles
    assert "Broadcast Sekolah" in titles
    assert "Kelas-D Sosial" not in titles


async def test_class_type_mismatch_and_untargeted_subject_hidden(client, engine):
    """A same class code but different programme, and untargeted subjects, are hidden."""
    await _register(client, "t_match@ex.com", "teacher")
    ok = await client.post(
        "/api/v1/courses",
        json={"title": "Mata Pelajaran IPA", "class_code": "1A", "class_type": "IPA"},
    )
    assert ok.status_code == 201, ok.text
    # A subject with no class_code must not leak to students even if published.
    untargeted = await client.post(
        "/api/v1/courses",
        json={"title": "Tanpa Kelas", "class_code": "UMUM"},
    )
    assert untargeted.status_code == 201, untargeted.text
    # Force a NULL class_code directly to simulate legacy data.
    from sqlalchemy import update

    from app.models.learning import Course

    async with engine.begin() as conn:
        await conn.execute(
            update(Course).where(Course.title == "Tanpa Kelas").values(class_code=None)
        )
    await client.post("/api/v1/auth/logout")

    # A student in 1A/IPS must NOT see the IPA subject (type mismatch).
    await _register(client, "s_1a_ips@ex.com", class_code="1A", class_type="IPS")
    subs = await client.get("/api/v1/courses")
    titles = {s["title"] for s in subs.json()}
    assert "Mata Pelajaran IPA" not in titles
    assert "Tanpa Kelas" not in titles


async def test_room_live_and_events_and_invite(client):
    await _register(client, "t_room_live@ex.com", "teacher")
    room = await client.post("/api/v1/rooms", json={"name": "Live Room"})
    room_id = room.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/open")

    live = await client.get(f"/api/v1/rooms/{room_id}/live")
    assert live.status_code == 200
    events = await client.get(f"/api/v1/rooms/{room_id}/events")
    assert events.status_code == 200
    assert any(e["event_type"] == "opened" for e in events.json())

    inv = await client.post(f"/api/v1/rooms/{room_id}/invite", json={"email": "guest@example.com"})
    assert inv.status_code == 200, inv.text
    code = inv.json()["code"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "guest_join@ex.com")
    accepted = await client.post("/api/v1/rooms/invitations/accept", json={"code": code})
    assert accepted.status_code == 200, accepted.text
    # Accepting the invitation must actually place the user in the room.
    assert accepted.json()["room_id"] == room_id
    members = await client.get(f"/api/v1/rooms/{room_id}/participants")
    assert members.status_code == 200, members.text
    guest = (await client.get("/api/v1/auth/me")).json()["id"]
    assert any(m["user_id"] == guest for m in members.json())


async def test_teacher_analytics_and_submissions(client):
    await _register(client, "t_analytics@ex.com", "teacher")
    analytics = await client.get("/api/v1/teacher/analytics")
    assert analytics.status_code == 200
    body = analytics.json()
    assert "exams" in body and "pass_rate_bp" in body

    subs = await client.get("/api/v1/teacher/submissions")
    assert subs.status_code == 200


async def test_muted_kind_suppresses_notification_creation(client):
    """GAME-14: a muted kind produces no Notification row for that kind."""
    await _register(client, "mute_owner@ex.com", "teacher")
    task = await client.post(
        "/api/v1/tasks", json={"title": "Mute test", "kind": "daily", "reward_amount": 5}
    )
    task_id = task.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "mute_student@ex.com", "student")

    before = await client.get("/api/v1/notifications/preferences")
    assert before.status_code == 200
    assert before.json()["muted_kinds"] == []

    muted = await client.put("/api/v1/notifications/preferences", json={"muted_kinds": ["reward"]})
    assert muted.status_code == 200, muted.text
    assert muted.json()["muted_kinds"] == ["reward"]

    complete = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert complete.status_code == 200, complete.text

    feed = await client.get("/api/v1/notifications")
    assert feed.status_code == 200
    # The task completion path notifies kind="reward" — must be suppressed.
    assert all(n["kind"] != "reward" for n in feed.json())


async def test_unmuting_a_kind_restores_delivery(client):
    await _register(client, "unmute_owner@ex.com", "teacher")
    task = await client.post(
        "/api/v1/tasks", json={"title": "Unmute test", "kind": "daily", "reward_amount": 5}
    )
    task_id = task.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "unmute_student@ex.com", "student")

    await client.put("/api/v1/notifications/preferences", json={"muted_kinds": ["reward"]})
    await client.put("/api/v1/notifications/preferences", json={"muted_kinds": []})

    complete = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert complete.status_code == 200, complete.text

    feed = await client.get("/api/v1/notifications")
    assert any(n["kind"] == "reward" for n in feed.json())


async def test_invalid_preferences_payload_rejected(client):
    await _register(client, "badprefs@ex.com", "student")
    r = await client.put("/api/v1/notifications/preferences", json={"muted_kinds": "not-a-list"})
    assert r.status_code == 422


async def test_muted_notification_service_returns_none(session):
    """Unit-level: NotificationService.notify() returns None when muted."""
    from app.models.social import NotificationPreference
    from app.services.social_service import NotificationService
    from tests.test_gamification import _user

    student = await _user(session, "mute_unit@q.com")
    session.add(NotificationPreference(user_id=student.id, muted_kinds=["quest"]))
    await session.flush()

    svc = NotificationService(session)
    muted_result = await svc.notify(user_id=student.id, kind="quest", title="x")
    assert muted_result is None

    allowed_result = await svc.notify(user_id=student.id, kind="reward", title="y")
    assert allowed_result is not None
