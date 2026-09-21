"""Tests for the social (notifications/badges) and new feature endpoints."""

from __future__ import annotations

import io

import pytest

from tests.pdf_util import make_pdf

pytestmark = pytest.mark.integration


async def _register(
    client, email, role="student", name="Test User", class_code=None, class_type=None
):
    payload = {"email": email, "full_name": name, "password": "Password123!", "role": role}
    if class_code:
        payload["class_code"] = class_code
    if class_type:
        payload["class_type"] = class_type
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


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
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin_b@ex.com",
            "full_name": "Admin B",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert r.status_code == 201
    # Promote to admin directly via DB is covered elsewhere; broadcast requires admin.
    # Here we only assert a non-admin is rejected and the endpoint exists.
    resp = await client.post("/api/v1/admin/notifications", json={"title": "Hi", "body": "all"})
    assert resp.status_code == 403


async def test_badge_catalog_available(client):
    await _register(client, "badge@ex.com")
    catalog = await client.get("/api/v1/badges")
    assert catalog.status_code == 200
    assert len(catalog.json()) >= 1
    # Each badge exposes its sequential on-chain id for display/linking.
    assert all("on_chain_id" in b for b in catalog.json())


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
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "t_class@ex.com",
            "full_name": "T Class",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert r.status_code == 201
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
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "t_match@ex.com",
            "full_name": "T Match",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert r.status_code == 201
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
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "t_room_live@ex.com",
            "full_name": "T Room Live",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert r.status_code == 201
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


async def test_teacher_analytics_and_submissions(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "t_analytics@ex.com",
            "full_name": "T Analytics",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert r.status_code == 201
    analytics = await client.get("/api/v1/teacher/analytics")
    assert analytics.status_code == 200
    body = analytics.json()
    assert "exams" in body and "pass_rate_bp" in body

    subs = await client.get("/api/v1/teacher/submissions")
    assert subs.status_code == 200
