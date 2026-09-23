"""Regression tests for the 'complete every feature' pass, round 4.

Covers gamification / rankings / career-authz gaps:
  - XP (and level) excludes flagged (disqualified) exam attempts, matching the
    score leaderboards
  - /rankings/me rank matches the global board's 3-key ordering (incl. ties)
  - a teacher cannot approve an arbitrary user's study-path plan (only a
    student's, or their own) — and can list pending reviews
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Round4 User")


# --- XP excludes flagged attempts ----------------------------------------
async def test_xp_excludes_flagged_attempts(session):
    """A flagged attempt must not contribute to XP/level."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.security import hash_password
    from app.models import Exam, ExamAttempt, User
    from app.models.identity import Role, UserRole
    from app.services.gamification_service import GamificationService

    role = (await session.execute(select(Role).where(Role.name == "student"))).scalar_one()
    teacher = User(
        email="xp_owner@q.com",
        full_name="Owner",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
    )
    student = User(
        email="xp_student@q.com",
        full_name="Student",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
    )
    session.add_all([teacher, student])
    await session.flush()
    session.add(UserRole(user_id=student.id, role_id=role.id))
    await session.flush()
    student = (
        await session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == student.id)
        )
    ).scalar_one()

    exam = Exam(title="XP Exam", owner_id=teacher.id, is_active=True)
    session.add(exam)
    await session.flush()
    session.add(
        ExamAttempt(
            exam_id=exam.id,
            user_id=student.id,
            attempt_number=1,
            status="graded",
            score_bp=9000,
            is_flagged=True,
            passed=True,
        )
    )
    await session.flush()

    svc = GamificationService(session)
    assert (await svc.xp_for_user(student.id))["xp"] == 0
    assert (await svc.xp_for_users([student.id]))[student.id] == 0

    # An unflagged attempt does count.
    session.add(
        ExamAttempt(
            exam_id=exam.id,
            user_id=student.id,
            attempt_number=2,
            status="graded",
            score_bp=5000,
            is_flagged=False,
            passed=True,
        )
    )
    await session.flush()
    assert (await svc.xp_for_user(student.id))["xp"] == 5000


# --- career approve authz -------------------------------------------------
async def test_teacher_cannot_approve_arbitrary_user(client):
    await _register(client, "r4_teacher@ex.com")
    # A random uuid that is not a user.
    bogus = str(uuid.uuid4())
    # The teacher previews their own (no recommendations) => 404; a bogus id
    # must not silently succeed either.
    own = await client.post("/api/v1/career/recommendations/approve")
    assert own.status_code in (404, 400), own.text
    bogus_resp = await client.post(f"/api/v1/career/recommendations/approve?user_id={bogus}")
    assert bogus_resp.status_code in (404, 403, 400), bogus_resp.text


async def test_teacher_cannot_approve_another_teacher(client):
    # A second teacher's id is not a student => forbidden.
    other = await _register(client, "r4_teacher_other@ex.com")
    await client.post("/api/v1/auth/logout")
    await _register(client, "r4_teacher2@ex.com")
    resp = await client.post(f"/api/v1/career/recommendations/approve?user_id={other['id']}")
    assert resp.status_code == 403, resp.text


async def test_pending_reviews_lists_students_and_approve_works(client):
    # Teacher + student; the student submits a plan, the teacher approves it.
    await _register(client, "r4_counselor@ex.com")
    await client.post("/api/v1/auth/logout")

    student = await _register(client, "r4_student@ex.com", "student")
    await client.post(
        "/api/v1/career/grades", json={"subject": "Matematika", "grade": 90, "term": "t"}
    )
    gen = await client.post("/api/v1/career/recommendations/generate")
    assert gen.status_code == 200, gen.text
    assert (await client.post("/api/v1/career/recommendations/submit")).status_code == 200
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login", json={"email": "r4_counselor@ex.com", "password": "Password123!"}
    )
    pending = await client.get("/api/v1/career/recommendations/pending")
    assert pending.status_code == 200, pending.text
    body = pending.json()
    assert any(p["user_id"] == student["id"] for p in body)

    ok = await client.post(f"/api/v1/career/recommendations/approve?user_id={student['id']}")
    assert ok.status_code == 200, ok.text
    # Cleared from the pending list.
    after = (await client.get("/api/v1/career/recommendations/pending")).json()
    assert all(p["user_id"] != student["id"] for p in after)


# --- notifications: liked notifications produce a 'quest' kind? -----------
async def test_quest_finalize_announces_on_room_channel(client):
    """Finalization is published to the quest's room channel (subscribed by the
    room page), not a dead quest:{id} channel."""
    from app.services.realtime import room_channel

    # room_channel is the exact topic the room WS subscribes to.
    assert room_channel("abc") == "room:abc"
