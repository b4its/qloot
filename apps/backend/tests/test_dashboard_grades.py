"""Dashboard grade edit and delete controls (UIX-05)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Grade User")


async def test_student_cannot_edit_or_delete_grade(client):
    await _register(client, "student_grade_actor@ex.com", role="student")
    created = await client.post(
        "/api/v1/career/grades",
        json={"subject": "Fisika", "grade": 70, "term": "2025/2026-genap"},
    )
    assert created.status_code == 200, created.text
    gid = created.json()["id"]

    # Student attempts to edit their grade -> 403 Forbidden
    edited = await client.put(f"/api/v1/career/grades/{gid}", json={"grade": 95})
    assert edited.status_code == 403, edited.text
    assert "guru dan admin" in edited.text or "teacher" in edited.text.lower()

    # Student attempts to delete their grade -> 403 Forbidden
    deleted = await client.delete(f"/api/v1/career/grades/{gid}")
    assert deleted.status_code == 403, deleted.text
    assert "guru dan admin" in deleted.text or "teacher" in deleted.text.lower()


async def test_teacher_can_edit_and_delete_grade(client):
    await _register(client, "student_target@ex.com", role="student")
    created = await client.post(
        "/api/v1/career/grades",
        json={"subject": "Kimia", "grade": 60, "term": "2025/2026-genap"},
    )
    assert created.status_code == 200, created.text
    gid = created.json()["id"]
    await client.post("/api/v1/auth/logout")

    # Teacher logs in and edits the student's grade -> 200 OK
    await _register(client, "teacher_grader@ex.com", role="teacher")
    edited = await client.put(f"/api/v1/career/grades/{gid}", json={"grade": 88})
    assert edited.status_code == 200, edited.text
    assert edited.json()["grade"] == 88

    # Teacher deletes the grade -> 200 OK
    deleted = await client.delete(f"/api/v1/career/grades/{gid}")
    assert deleted.status_code == 200, deleted.text


async def test_admin_can_edit_and_delete_grade(client):
    await _register(client, "student_target_adm@ex.com", role="student")
    created = await client.post(
        "/api/v1/career/grades",
        json={"subject": "Biologi", "grade": 75, "term": "2025/2026-genap"},
    )
    assert created.status_code == 200, created.text
    gid = created.json()["id"]
    await client.post("/api/v1/auth/logout")

    # Admin logs in and edits the student's grade -> 200 OK
    await _register(client, "admin_grader@ex.com", role="admin")
    edited = await client.put(f"/api/v1/career/grades/{gid}", json={"grade": 92})
    assert edited.status_code == 200, edited.text
    assert edited.json()["grade"] == 92

    # Admin deletes the grade -> 200 OK
    deleted = await client.delete(f"/api/v1/career/grades/{gid}")
    assert deleted.status_code == 200, deleted.text
