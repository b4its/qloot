"""Regression tests for the 'complete every feature' pass, round 7.

Covers features that had a read/display path but no write/trigger path:
  - certificate revocation (admin) flips verify to invalid + hides from list
  - a stored material can be downloaded (upload had no read-back)
  - XP-milestone badges are actually earnable (no permanent filler)
  - a graded exam notifies the student
  - finalising a quest notifies non-winning participants ('quest' kind)
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Round7 User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _make_admin(client, email):
    """Register then promote to admin (registration can't self-assign admin)."""
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models.identity import Role, UserRole

    user = await _register(client, email, "teacher")
    sm = get_sessionmaker()
    async with sm() as s:
        role = (await s.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        s.add(UserRole(user_id=uuid.UUID(user["id"]), role_id=role.id))
        await s.commit()
    await client.post("/api/v1/auth/logout")
    await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return user


async def _earn_certificate(
    client, *, class_code="7Z", title="Kursus R7", full_name="Budi Santoso", email="r7_stu@ex.com"
):
    """Teacher builds a course+lesson; student completes it and a cert is issued."""
    course = await client.post(
        "/api/v1/courses",
        json={"title": title, "class_code": class_code, "class_type": "IPA", "is_published": True},
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
            "email": email,
            "full_name": full_name,
            "password": "Password123!",
            "role": "student",
            "class_code": class_code,
            "class_type": "IPA",
        },
    )
    await client.post(
        f"/api/v1/lessons/{lid}/progress", json={"completed": True, "progress_percent": 100}
    )
    certs = await client.get("/api/v1/certificates")
    assert certs.json(), certs.text
    return certs.json()[0]


# --- certificate revoke ----------------------------------------------------
async def test_admin_can_revoke_certificate(client):
    await _register(client, "r7_ct@ex.com")
    cert = await _earn_certificate(client)
    cred = cert["credential_id"]
    await client.post("/api/v1/auth/logout")

    await _make_admin(client, "r7_admin@ex.com")
    rev = await client.post(f"/api/v1/certificates/{cred}/revoke", json={"reason": "Terbit keliru"})
    assert rev.status_code == 200, rev.text
    assert rev.json()["revoked_at"] is not None
    assert rev.json()["revoked_reason"] == "Terbit keliru"

    # Public verify now reports invalid.
    v = await client.get(f"/api/v1/certificates/verify/{cred}")
    assert v.json()["valid"] is False
    # Idempotent re-revoke.
    again = await client.post(f"/api/v1/certificates/{cred}/revoke", json={})
    assert again.status_code == 200, again.text


async def test_student_cannot_revoke_certificate(client):
    await _register(client, "r7_ct2@ex.com")
    cert = await _earn_certificate(
        client, class_code="7Y", title="Kursus R7b", email="r7_stu2@ex.com"
    )
    # Still logged in as the student.
    resp = await client.post(f"/api/v1/certificates/{cert['credential_id']}/revoke", json={})
    assert resp.status_code in (401, 403), resp.text


# --- material download -----------------------------------------------------
async def test_material_can_be_downloaded(client):
    from tests.pdf_util import make_pdf

    await _register(client, "r7_mat@ex.com")
    pdf = make_pdf("Materi untuk diunduh: fisika dasar dan energi.")
    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("fisika.pdf", pdf, "application/pdf")},
    )
    assert up.status_code == 201, up.text
    material_id = up.json()["id"]

    dl = await client.get(f"/api/v1/materials/{material_id}/download")
    assert dl.status_code == 200, dl.text
    assert dl.content == pdf
    assert "attachment" in dl.headers.get("content-disposition", "")
    assert dl.headers.get("content-type", "").startswith("application/pdf")


async def test_material_download_requires_access(client):
    from tests.pdf_util import make_pdf

    await _register(client, "r7_mat2@ex.com")
    material_id = (
        await client.post(
            "/api/v1/materials/upload",
            files={"file": ("m.pdf", make_pdf("Rahasia."), "application/pdf")},
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "r7_other@ex.com")
    denied = await client.get(f"/api/v1/materials/{material_id}/download")
    assert denied.status_code in (403, 404), denied.text


# --- XP milestone badges ---------------------------------------------------
async def test_xp_milestone_badges_are_earnable(client):
    """A user with enough XP gets the milestone badge; catalog has no achv-* filler."""
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models.social import Badge

    # The catalog must not contain the old unreachable filler.
    sm = get_sessionmaker()
    await client.get("/api/v1/badges")  # triggers ensure_catalog
    async with sm() as s:
        codes = {c for (c,) in (await s.execute(select(Badge.code))).all()}
    assert not any(c.startswith("achv-") for c in codes)

    # A user with >= 500 XP earns xp_500 via /gamification/me.
    me = await _register(client, "r7_xp@ex.com", "student")
    from app.db.session import get_sessionmaker as _sm

    sm = _sm()
    async with sm() as s:
        from app.models.exam import Exam, ExamAttempt
        from app.models.identity import User

        u = (await s.execute(select(User).where(User.id == uuid.UUID(me["id"])))).scalar_one()
        exam = Exam(title="XP Exam R7", owner_id=u.id, is_active=True)
        s.add(exam)
        await s.flush()
        s.add(
            ExamAttempt(
                exam_id=exam.id,
                user_id=u.id,
                attempt_number=1,
                status="graded",
                score_bp=900,  # > 500 XP (1 XP per bp)
                passed=True,
            )
        )
        await s.commit()

    g = await client.get("/api/v1/gamification/me")
    assert g.status_code == 200, g.text
    assert g.json()["xp"] >= 500
    badges = await client.get("/api/v1/me/badges")
    codes = {b["badge"]["code"] for b in badges.json()}
    assert "xp_500" in codes, badges.text


# --- grading notification --------------------------------------------------
async def test_graded_exam_notifies_student(client):
    await _register(client, "r7_gt@ex.com")
    exam = await client.post("/api/v1/exams", json={"title": "Notif Exam", "duration_minutes": 10})
    exam_id = exam.json()["id"]
    qid = (
        await client.post(
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
    ).json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "r7_gs@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")  # MC-only => graded inline

    notes = await client.get("/api/v1/notifications")
    assert any("Nilai ujian" in n["title"] for n in notes.json()), notes.text


# --- quest participant notification ---------------------------------------
async def test_quest_finalize_notifies_non_winners(client):
    await _register(client, "r7_qt@ex.com")
    exam = await client.post(
        "/api/v1/exams", json={"title": "Quest Exam R7", "duration_minutes": 10}
    )
    exam_id = exam.json()["id"]
    qid = (
        await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={
                "prompt": "2 + 2?",
                "qtype": "multiple_choice",
                "position": 0,
                "options": [
                    {"text": "4", "is_correct": True},
                    {"text": "5", "is_correct": False},
                ],
            },
        )
    ).json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    quest_id = (
        await client.post(
            "/api/v1/quests",
            json={
                "title": "Quest R7",
                "exam_id": exam_id,
                "top_n_winners": 1,
                "rules": [{"rank": 1, "reward_amount": 5}],
            },
        )
    ).json()["id"]
    await client.post(f"/api/v1/quests/{quest_id}/publish")
    await client.post("/api/v1/auth/logout")

    # Two students attempt; loser should get a "quest" notification.
    await _register(client, "r7_qs1@ex.com", "student")
    a1 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a1}/answers/{qid}", json={"answer_text": "A"})
    await client.post(f"/api/v1/attempts/{a1}/submit")
    await client.post("/api/v1/auth/logout")

    await _register(client, "r7_qs2@ex.com", "student")
    a2 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a2}/answers/{qid}", json={"answer_text": "B"})
    await client.post(f"/api/v1/attempts/{a2}/submit")
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login", json={"email": "r7_qt@ex.com", "password": "Password123!"}
    )
    fin = await client.post(f"/api/v1/quests/{quest_id}/finalize")
    assert fin.status_code == 200, fin.text
    await client.post("/api/v1/auth/logout")

    # The losing student (wrong answer) should have a quest notification.
    await client.post(
        "/api/v1/auth/login", json={"email": "r7_qs2@ex.com", "password": "Password123!"}
    )
    notes = await client.get("/api/v1/notifications")
    assert any(n["kind"] == "quest" for n in notes.json()), notes.text
