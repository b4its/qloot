"""Exam-attempt listing scoped to one exam (``GET /attempts?exam_id=``).

An exam detail page needs only its own attempts (best score, resume pointer);
the endpoint supports ``exam_id`` so the client never over-fetches the whole
history and filters client-side.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _mk_user(session):
    from tests.conftest import provision_user

    return await provision_user(session, email=f"att_{uuid.uuid4().hex[:8]}@ex.com")


async def _mk_exam(session, owner_id) -> uuid.UUID:
    from app.models.exam import Exam

    exam_id = uuid.uuid4()
    session.add(
        Exam(
            id=exam_id,
            title="E",
            owner_id=owner_id,
            duration_minutes=30,
            status="published",
            is_active=True,
            passing_score_bp=6000,
        )
    )
    await session.flush()
    return exam_id


async def _mk_attempt(session, exam_id, user_id, number: int) -> None:
    from app.models.exam import ExamAttempt

    session.add(
        ExamAttempt(
            id=uuid.uuid4(),
            exam_id=exam_id,
            user_id=user_id,
            attempt_number=number,
            status="graded",
        )
    )
    await session.flush()


async def test_attempts_can_be_scoped_to_one_exam(client, session):
    user = await _mk_user(session)
    e1 = await _mk_exam(session, user.id)
    e2 = await _mk_exam(session, user.id)
    await _mk_attempt(session, e1, user.id, 1)
    await _mk_attempt(session, e1, user.id, 2)
    await _mk_attempt(session, e2, user.id, 1)
    await session.commit()

    login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "Password123!"}
    )
    assert login.status_code == 200, login.text

    r = await client.get(f"/api/v1/attempts?exam_id={e1}")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2
    assert all(row["exam_id"] == str(e1) for row in rows)

    # Without the filter, all three appear.
    allrows = (await client.get("/api/v1/attempts?limit=200")).json()
    exam_ids = {row["exam_id"] for row in allrows}
    assert {str(e1), str(e2)} <= exam_ids
