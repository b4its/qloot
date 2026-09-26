"""Counselor-side consultation workflow tests (CARE-06)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Consult User")


async def _login(client, email, password="Password123!"):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


async def test_counselors_are_real_teacher_users(client):
    """The counselor list is backed by real teacher accounts, not a tuple."""
    teacher = await _register(client, "cons_teacher@ex.com", "teacher")
    await client.post("/api/v1/auth/logout")

    await _register(client, "cons_student@ex.com", "student")
    r = await client.get("/api/v1/career/counselors")
    assert r.status_code == 200, r.text
    ids = [c["user_id"] for c in r.json()]
    assert teacher["id"] in ids


async def test_student_books_a_specific_counselor_and_slot(client):
    teacher = await _register(client, "cons_t2@ex.com", "teacher")
    await client.post("/api/v1/auth/logout")
    await _register(client, "cons_student2@ex.com", "student")

    r = await client.post(
        "/api/v1/career/consultations",
        json={
            "counselor_user_id": teacher["id"],
            "topic": "Pilihan jurusan",
            "scheduled_at": "2026-10-01T02:00:00Z",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counselor_user_id"] == teacher["id"]
    assert body["status"] == "pending"


async def test_teacher_accepts_and_completes_a_consultation(client):
    teacher = await _register(client, "cons_t3@ex.com", "teacher")
    await client.post("/api/v1/auth/logout")
    await _register(client, "cons_student3@ex.com", "student")
    cid = (
        await client.post(
            "/api/v1/career/consultations",
            json={"counselor_user_id": teacher["id"], "topic": "SNBP"},
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    # Teacher logs in and manages the request.
    await _login(client, "cons_t3@ex.com")
    managed = await client.get("/api/v1/career/consultations/managed")
    assert managed.status_code == 200, managed.text
    target_c = next(c for c in managed.json() if c["id"] == cid)
    assert target_c["student_name"] == "Consult User"

    acc = await client.post(f"/api/v1/career/consultations/{cid}/accept")
    assert acc.status_code == 200, acc.text
    assert acc.json()["status"] == "accepted"

    done = await client.post(f"/api/v1/career/consultations/{cid}/complete")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    assert done.json()["completed_at"] is not None


async def test_consultation_thread_is_two_way_and_scoped(client):
    teacher = await _register(client, "cons_t4@ex.com", "teacher")
    await client.post("/api/v1/auth/logout")
    await _register(client, "cons_student4@ex.com", "student")
    cid = (
        await client.post(
            "/api/v1/career/consultations",
            json={"counselor_user_id": teacher["id"], "topic": "Nilai"},
        )
    ).json()["id"]

    # Student posts a message.
    m = await client.post(
        f"/api/v1/career/consultations/{cid}/messages", json={"body": "Halo Bu/Bapak"}
    )
    assert m.status_code == 201, m.text
    assert m.json()["sender_name"] == "Consult User"
    thread = await client.get(f"/api/v1/career/consultations/{cid}/messages")
    assert len(thread.json()) == 1
    assert thread.json()[0]["sender_name"] == "Consult User"

    # A different student cannot read or write the thread.
    await client.post("/api/v1/auth/logout")
    await _register(client, "cons_other@ex.com", "student")
    assert (
        await client.get(f"/api/v1/career/consultations/{cid}/messages")
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/career/consultations/{cid}/messages", json={"body": "x"}
        )
    ).status_code == 404


async def test_completed_consultation_cannot_be_cancelled(client):
    teacher = await _register(client, "cons_t5@ex.com", "teacher")
    await client.post("/api/v1/auth/logout")
    await _register(client, "cons_student5@ex.com", "student")
    cid = (
        await client.post(
            "/api/v1/career/consultations",
            json={"counselor_user_id": teacher["id"], "topic": "Selesai"},
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _login(client, "cons_t5@ex.com")
    await client.post(f"/api/v1/career/consultations/{cid}/complete")
    await client.post("/api/v1/auth/logout")

    await _login(client, "cons_student5@ex.com")
    cancel = await client.post(f"/api/v1/career/consultations/{cid}/cancel")
    assert cancel.status_code == 409, cancel.text
