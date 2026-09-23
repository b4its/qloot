"""Expired-attempt sweeper: auto-submit and grading enqueue (C19)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.exam import ExamAttempt, GradingJob
from app.services.exam_service import ExamService
from tests.helpers import register_actor

pytestmark = pytest.mark.integration


async def _make_exam_with_essay(client) -> tuple[str, str]:
    exam = await client.post(
        "/api/v1/exams",
        json={"title": "Sweeper Exam", "duration_minutes": 30, "passing_score_bp": 5000},
    )
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Jelaskan AI.", "correct_answer": "AI", "position": 0},
    )
    qid = q.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id, qid


async def test_sweeper_auto_submits_expired_attempt_and_is_idempotent(client, engine):
    await register_actor(client, "sw_teacher@ex.com", "teacher")
    exam_id, _qid = await _make_exam_with_essay(client)
    await client.post("/api/v1/auth/logout")

    await register_actor(client, "sw_student@ex.com", "student")
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = attempt.json()["id"]

    # Force expiry.
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        await s.execute(
            update(ExamAttempt)
            .where(ExamAttempt.id == uuid.UUID(attempt_id))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()

    # First sweep submits it and queues grading.
    async with sm() as s:
        n = await ExamService(s).sweep_expired_attempts()
        await s.commit()
    assert n >= 1

    async with sm() as s:
        row = await s.get(ExamAttempt, uuid.UUID(attempt_id))
        assert row.status == "submitted"
        assert row.submitted_at is not None
        jobs = (
            await s.execute(select(GradingJob).where(GradingJob.attempt_id == uuid.UUID(attempt_id)))
        ).scalars().all()
    assert len(jobs) == 1

    # Second sweep must not duplicate our attempt's grading job.
    async with sm() as s:
        await ExamService(s).sweep_expired_attempts()
        await s.commit()

    async with sm() as s:
        jobs2 = (
            await s.execute(select(GradingJob).where(GradingJob.attempt_id == uuid.UUID(attempt_id)))
        ).scalars().all()
    assert len(jobs2) == 1


async def test_sweeper_ignores_non_expired_attempts(client, engine):
    await register_actor(client, "sw2_teacher@ex.com", "teacher")
    exam_id, _ = await _make_exam_with_essay(client)
    await client.post("/api/v1/auth/logout")
    await register_actor(client, "sw2_student@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        await ExamService(s).sweep_expired_attempts()
        await s.commit()

    # Our attempt (deadline still in the future) is untouched.
    async with sm() as s:
        row = await s.get(ExamAttempt, uuid.UUID(attempt_id))
        assert row.status == "in_progress"
