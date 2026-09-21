"""Worker loop: claim a job, release its lock, process it in a fresh tx.

Validates the refactor that moved the slow AI call out of the claim
transaction (previously the job's FOR UPDATE lock + a pool connection were held
for the whole provider call).

The suite shares one database, so these tests clear any leftover queued jobs
first and drain the queue deterministically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.exam import Exam, ExamAttempt, GradingJob, Question, StudentAnswer

pytestmark = pytest.mark.integration


async def _clear_queued_jobs(session):
    from sqlalchemy import delete

    await session.execute(delete(GradingJob).where(GradingJob.status == "queued"))
    await session.flush()


async def _seed_grading_job(session):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.security import hash_password
    from app.models.identity import Role, User, UserRole

    role = (await session.execute(select(Role).where(Role.name == "student"))).scalar_one()
    student = User(
        email=f"wloop_{uuid.uuid4().hex[:6]}@q.com",
        full_name="Worker Loop",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + (uuid.uuid4().hex + uuid.uuid4().hex)[:64],
    )
    session.add(student)
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

    exam = Exam(title="Worker Loop Exam", owner_id=student.id, is_active=True)
    session.add(exam)
    await session.flush()
    question = Question(
        exam_id=exam.id,
        owner_id=student.id,
        prompt="Apa itu energi?",
        correct_answer="Kapasitas melakukan kerja",
        source="manual",
        review_status="approved",
        position=0,
    )
    session.add(question)
    await session.flush()

    attempt = ExamAttempt(
        exam_id=exam.id,
        user_id=student.id,
        attempt_number=1,
        status="submitted",
        submitted_at=datetime.now(UTC),
    )
    session.add(attempt)
    await session.flush()
    session.add(
        StudentAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_text="Kapasitas melakukan kerja",
        )
    )
    job = GradingJob(attempt_id=attempt.id, owner_id=student.id, kind="grading", status="queued")
    session.add(job)
    await session.flush()
    return student, attempt, job


async def test_worker_processes_grading_job_and_clears_lock(engine, session):
    """_process_once grades the queued attempt and leaves the job in 'done'."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.workers.main import _process_once

    await _clear_queued_jobs(session)
    _, attempt, job = await _seed_grading_job(session)
    await session.commit()

    processed = await _process_once()
    assert processed is True

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        fresh_job = (
            await s.execute(select(GradingJob).where(GradingJob.id == job.id))
        ).scalar_one()
        fresh_attempt = (
            await s.execute(select(ExamAttempt).where(ExamAttempt.id == attempt.id))
        ).scalar_one()
        assert fresh_job.status == "done"
        assert fresh_job.started_at is not None
        assert fresh_attempt.status == "graded"
        assert fresh_attempt.score_bp is not None


async def test_worker_returns_false_when_no_jobs(engine, session):
    from app.workers.main import _process_once

    # Drain any queued jobs first so this test is order-independent.
    await _clear_queued_jobs(session)
    await session.commit()

    assert await _process_once() is False
