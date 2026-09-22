"""Regression tests for the 'complete every feature' pass, round 6.

Covers exam-lifecycle, certificate and grading-integrity gaps:
  - a student cannot grade (finalise) their own *in-progress* attempt
  - exam scheduling windows (opens_at/closes_at) are settable and enforced
  - the public certificate verify masks the recipient surname
  - certificate issuance notifies the learner
  - a grading result is unique per job (reaper requeue can't duplicate)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Round6 User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _mc_exam(client, *, opens_at=None, closes_at=None, publish=True):
    payload = {"title": "R6 Exam", "duration_minutes": 15}
    if opens_at is not None:
        payload["opens_at"] = opens_at
    if closes_at is not None:
        payload["closes_at"] = closes_at
    exam = await client.post("/api/v1/exams", json=payload)
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Ibu kota Indonesia?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [
                {"text": "Jakarta", "is_correct": True},
                {"text": "Bandung", "is_correct": False},
            ],
        },
    )
    qid = q.json()["id"]
    if publish:
        pub = await client.post(f"/api/v1/exams/{exam_id}/publish")
        assert pub.status_code == 200, pub.text
    return exam_id, qid


# --- student cannot self-grade an in-progress attempt ---------------------
async def test_student_cannot_grade_in_progress_attempt(client):
    await _register(client, "r6_t1@ex.com")
    exam_id, qid = await _mc_exam(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "r6_s1@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"})
    # Attempt is still in_progress => student may NOT grade it.
    grade = await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})
    assert grade.status_code == 409, grade.text
    # The attempt is still editable (not finalised).
    still = await client.get(f"/api/v1/attempts/{attempt_id}")
    assert still.json()["status"] == "in_progress"


# --- scheduling window enforcement ----------------------------------------
async def test_exam_not_open_before_opens_at(client):
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    await _register(client, "r6_t2@ex.com")
    exam_id, _ = await _mc_exam(client, opens_at=future)
    await client.post("/api/v1/auth/logout")

    await _register(client, "r6_s2@ex.com", "student")
    resp = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    assert resp.status_code == 409, resp.text
    assert "dibuka" in resp.json()["error"]["message"].lower()


async def test_exam_rejects_attempt_after_closes_at(client):
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    await _register(client, "r6_t3@ex.com")
    exam_id, _ = await _mc_exam(client, closes_at=past)
    await client.post("/api/v1/auth/logout")

    await _register(client, "r6_s3@ex.com", "student")
    resp = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    assert resp.status_code == 409, resp.text


async def test_exam_within_window_allows_attempt(client):
    opens = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    closes = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    await _register(client, "r6_t4@ex.com")
    exam_id, _ = await _mc_exam(client, opens_at=opens, closes_at=closes)
    await client.post("/api/v1/auth/logout")

    await _register(client, "r6_s4@ex.com", "student")
    resp = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    assert resp.status_code == 201, resp.text


# --- certificate masking + notification -----------------------------------
async def test_public_verify_masks_recipient_name(client):
    await _register(client, "r6_ct@ex.com", "teacher")
    course = await client.post(
        "/api/v1/courses",
        json={
            "title": "Kursus Sertifikat R6",
            "class_code": "9Z",
            "class_type": "IPA",
            "is_published": True,
        },
    )
    cid = course.json()["id"]
    lid = (
        await client.post(
            f"/api/v1/courses/{cid}/lessons",
            json={"title": "L1", "content": "x", "position": 0, "is_published": True},
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    # Student with a two-word name so masking is observable.
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "r6_cs2@ex.com",
            "full_name": "Budi Santoso",
            "password": "Password123!",
            "role": "student",
            "class_code": "9Z",
            "class_type": "IPA",
        },
    )
    assert r.status_code == 201, r.text
    await client.post(
        f"/api/v1/lessons/{lid}/progress", json={"completed": True, "progress_percent": 100}
    )
    certs = await client.get("/api/v1/certificates")
    assert certs.json(), certs.text
    cred = certs.json()[0]["credential_id"]

    await client.post("/api/v1/auth/logout")
    verify = await client.get(f"/api/v1/certificates/verify/{cred}")
    assert verify.status_code == 200, verify.text
    body = verify.json()
    assert body["valid"] is True
    assert body["recipient_name"] == "Budi S."
    assert "Santoso" not in body["recipient_name"]


async def test_certificate_issuance_notifies_learner(client):
    await _register(client, "r6_nt@ex.com", "teacher")
    course = await client.post(
        "/api/v1/courses",
        json={
            "title": "Kursus Notif R6",
            "class_code": "8Y",
            "class_type": "IPA",
            "is_published": True,
        },
    )
    cid = course.json()["id"]
    lid = (
        await client.post(
            f"/api/v1/courses/{cid}/lessons",
            json={"title": "L1", "content": "x", "position": 0, "is_published": True},
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "r6_ns@ex.com",
            "full_name": "Notif Siswa",
            "password": "Password123!",
            "role": "student",
            "class_code": "8Y",
            "class_type": "IPA",
        },
    )
    await client.post(
        f"/api/v1/lessons/{lid}/progress", json={"completed": True, "progress_percent": 100}
    )
    await client.get("/api/v1/certificates")  # triggers issuance
    notes = await client.get("/api/v1/notifications")
    assert any("Sertifikat" in n["title"] for n in notes.json()), notes.text


# --- grading result uniqueness --------------------------------------------
async def test_grading_result_unique_per_job(session):
    from sqlalchemy.exc import IntegrityError

    from app.core.security import hash_password
    from app.models.exam import Exam, ExamAttempt, GradingJob, GradingResult
    from app.models.identity import User

    u = User(
        email="gr@q.com",
        full_name="GR",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
    )
    session.add(u)
    await session.flush()
    exam = Exam(title="GR", owner_id=u.id)
    session.add(exam)
    await session.flush()
    att = ExamAttempt(exam_id=exam.id, user_id=u.id, attempt_number=1, status="submitted")
    session.add(att)
    await session.flush()
    job = GradingJob(owner_id=None, kind="grading", status="queued")
    session.add(job)
    await session.flush()

    session.add(GradingResult(job_id=job.id, attempt_id=att.id, model="mock"))
    await session.flush()
    # A second result for the same job must violate uq_grading_results_job.
    session.add(GradingResult(job_id=job.id, attempt_id=att.id, model="mock"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()
