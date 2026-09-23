"""Security regressions: exam/material visibility and answer-key leakage.

Covers fixes where `/exams/{id}` and `/materials/{id}` had no ownership or
visibility checks, exposing drafts and answer keys to any authenticated user.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Test User")


async def _make_exam(client, title="Ujian Rahasia", publish=False):
    exam = await client.post("/api/v1/exams", json={"title": title, "duration_minutes": 30})
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Apa itu energi?", "correct_answer": "Kapasitas melakukan kerja"},
    )
    assert q.status_code == 201, q.text
    if publish:
        assert (await client.post(f"/api/v1/exams/{exam_id}/publish")).status_code == 200
    return exam_id


async def test_student_cannot_read_unpublished_exam(client):
    await _register(client, "exam_owner@ex.com", "teacher")
    exam_id = await _make_exam(client, publish=False)
    await client.post("/api/v1/auth/logout")

    await _register(client, "exam_pry@ex.com", "student")
    r = await client.get(f"/api/v1/exams/{exam_id}")
    # A draft exam must not be readable by a student.
    assert r.status_code == 404, r.text


async def test_student_never_sees_answer_key(client):
    await _register(client, "exam_owner2@ex.com", "teacher")
    exam_id = await _make_exam(client, publish=True)
    await client.post("/api/v1/auth/logout")

    await _register(client, "exam_taker@ex.com", "student")
    r = await client.get(f"/api/v1/exams/{exam_id}")
    assert r.status_code == 200, r.text
    questions = r.json()["questions"]
    assert questions, "published exam should expose questions"
    assert all(q["correct_answer"] is None for q in questions)


async def test_owner_still_sees_answer_key(client):
    await _register(client, "exam_owner3@ex.com", "teacher")
    exam_id = await _make_exam(client, publish=False)
    r = await client.get(f"/api/v1/exams/{exam_id}")
    assert r.status_code == 200, r.text
    questions = r.json()["questions"]
    assert questions[0]["correct_answer"] == "Kapasitas melakukan kerja"


async def test_material_detail_requires_view_permission(client):
    # Owner uploads a material, then an unrelated student tries to read it by id.
    await _register(client, "mat_owner@ex.com", "teacher")
    from tests.pdf_util import make_pdf

    files = {"file": ("m.pdf", make_pdf("Materi rahasia tentang fisika kuantum."), "application/pdf")}
    up = await client.post("/api/v1/materials/upload", files=files)
    assert up.status_code == 201, up.text
    material_id = up.json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "mat_pry@ex.com", "student")
    r = await client.get(f"/api/v1/materials/{material_id}")
    assert r.status_code in (403, 404), r.text
