"""Exam lifecycle: create, publish, attempt, autosave, submit, grade."""

from __future__ import annotations

import io

import pytest

from tests.pdf_util import make_pdf

pytestmark = pytest.mark.integration


async def _register(client, email, role):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _make_pdf() -> bytes:
    return make_pdf("Pembelajaran mesin adalah cabang kecerdasan buatan (artificial intelligence).")


async def test_full_exam_flow(client):
    # Teacher sets up an exam.
    await _register(client, "teacher@ex.com", "teacher")
    exam = await client.post(
        "/api/v1/exams",
        json={"title": "Ujian AI", "duration_minutes": 30, "passing_score_bp": 5000},
    )
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]

    q1 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Apa itu machine learning?", "correct_answer": "Cabang AI", "position": 0},
    )
    assert q1.status_code == 201, q1.text
    q2 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Sebutkan contoh", "correct_answer": "Klasifikasi", "position": 1},
    )
    assert q2.status_code == 201
    question_ids = [q1.json()["id"], q2.json()["id"]]

    pub = await client.post(f"/api/v1/exams/{exam_id}/publish")
    assert pub.status_code == 200
    assert pub.json()["is_active"] is True

    await client.post("/api/v1/auth/logout")

    # Student takes the exam.
    await _register(client, "student@ex.com", "student")
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    assert attempt.status_code == 201, attempt.text
    attempt_id = attempt.json()["id"]

    for qid in question_ids:
        resp = await client.put(
            f"/api/v1/attempts/{attempt_id}/answers/{qid}",
            json={"answer_text": "Machine learning adalah cabang AI untuk klasifikasi."},
        )
        assert resp.status_code == 200, resp.text

    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit.status_code == 200
    assert submit.json()["submitted_at"] is not None

    # Idempotent submit.
    submit2 = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit2.status_code == 200

    # Grade synchronously via the AI endpoint.
    grade = await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})
    assert grade.status_code == 200, grade.text
    items = grade.json()
    assert len(items) == 2
    assert all(i["score_bp"] is not None for i in items)

    result = await client.get(f"/api/v1/attempts/{attempt_id}/result")
    assert result.status_code == 200
    body = result.json()
    assert body["attempt"]["status"] == "graded"
    assert body["attempt"]["score_bp"] is not None


async def test_get_exam_detail_in_fresh_session(client):
    """GET /exams/{id} after questions exist must not lazy-load on serialize.

    The frontend exam page loads this endpoint directly; a MissingGreenlet on
    the ``questions`` relationship used to surface as "Failed to load exam".
    """
    await _register(client, "detail@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "Detail Exam"})
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Apa itu gaya?", "correct_answer": "interaksi"},
    )
    assert q.status_code == 201, q.text
    await client.post(f"/api/v1/exams/{exam_id}/publish")

    # A separate request = separate DB session, so the questions relationship
    # is not already populated in the identity map.
    detail = await client.get(f"/api/v1/exams/{exam_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == exam_id
    assert body["title"] == "Detail Exam"
    assert len(body["questions"]) == 1
    assert body["questions"][0]["prompt"] == "Apa itu gaya?"

    # Listing exams must also serialize cleanly (no relationship access).
    listed = await client.get("/api/v1/exams")
    assert listed.status_code == 200, listed.text
    assert any(e["id"] == exam_id for e in listed.json())


async def test_get_quest_detail_in_fresh_session(client):
    """GET /quests/{id} must not lazy-load its rules relationship on serialize."""
    await _register(client, "quest_detail@ex.com", "teacher")
    created = await client.post(
        "/api/v1/quests",
        json={
            "title": "Quest Detail",
            "kind": "exam",
            "rules": [
                {"rank": 1, "reward_amount": 300},
                {"rank": 2, "reward_amount": 150},
            ],
        },
    )
    assert created.status_code == 201, created.text
    quest_id = created.json()["id"]

    # A separate request = separate DB session; the rules relationship is not
    # pre-populated, so validating QuestDetailOut would lazy-load without this fix.
    detail = await client.get(f"/api/v1/quests/{quest_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == quest_id
    assert len(body["rules"]) == 2
    assert {r["rank"] for r in body["rules"]} == {1, 2}

    # Listing quests must also serialize cleanly.
    listed = await client.get("/api/v1/quests")
    assert listed.status_code == 200, listed.text
    assert any(q["id"] == quest_id for q in listed.json())


async def test_student_cannot_read_other_students_attempt(client):
    await _register(client, "t2@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "E2"})
    exam_id = exam.json()["id"]
    await client.post(
        f"/api/v1/exams/{exam_id}/questions", json={"prompt": "Q?", "correct_answer": "A"}
    )
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_a@ex.com", "student")
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = attempt.json()["id"]
    await client.post("/api/v1/auth/logout")

    # Another student must not read the first student's attempt.
    await _register(client, "s_b@ex.com", "student")
    resp = await client.get(f"/api/v1/attempts/{attempt_id}")
    assert resp.status_code == 403


async def test_teacher_cannot_edit_other_teachers_exam(client):
    await _register(client, "owner@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "Owned"})
    exam_id = exam.json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "intruder@ex.com", "teacher")
    resp = await client.patch(f"/api/v1/exams/{exam_id}", json={"title": "Hijacked"})
    assert resp.status_code == 403


async def test_material_upload_and_generation(client, tmp_path):
    await _register(client, "m@ex.com", "teacher")
    pdf = await _make_pdf()
    resp = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("materi.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    material_id = resp.json()["id"]

    gen = await client.post(
        f"/api/v1/materials/{material_id}/generate-questions-sync",
        json={"count": 3, "language": "id"},
    )
    assert gen.status_code == 200, gen.text
    questions = gen.json()
    assert len(questions) == 3
    # AI-generated questions must await teacher review.
    assert all(q["review_status"] == "pending" for q in questions)


async def test_reject_non_pdf_upload(client):
    await _register(client, "bad@ex.com", "teacher")
    resp = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("evil.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
    )
    assert resp.status_code == 422
