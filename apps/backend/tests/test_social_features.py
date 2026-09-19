"""Tests for the social (notifications/badges) and new feature endpoints."""

from __future__ import annotations

import io

import pytest

from tests.pdf_util import make_pdf

pytestmark = pytest.mark.integration


async def _register(client, email, role="student", name="Test User"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": "Password123!", "role": role},
    )
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
    resp = await client.post(
        "/api/v1/admin/notifications", json={"title": "Hi", "body": "all"}
    )
    assert resp.status_code == 403


async def test_badge_catalog_available(client):
    await _register(client, "badge@ex.com")
    catalog = await client.get("/api/v1/badges")
    assert catalog.status_code == 200
    assert len(catalog.json()) >= 1


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


async def test_course_enroll_and_list(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "t_enroll@ex.com",
            "full_name": "T Enroll",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert r.status_code == 201
    course = await client.post(
        "/api/v1/courses", json={"title": "Enroll Course", "description": "x"}
    )
    course_id = course.json()["id"]
    await client.patch(f"/api/v1/courses/{course_id}", json={"is_published": True})
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_enroll@ex.com")
    enr = await client.post(f"/api/v1/courses/{course_id}/enroll")
    assert enr.status_code == 200, enr.text
    mine = await client.get("/api/v1/me/enrollments")
    assert any(e["course_id"] == course_id for e in mine.json())


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

    inv = await client.post(
        f"/api/v1/rooms/{room_id}/invite", json={"email": "guest@example.com"}
    )
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
