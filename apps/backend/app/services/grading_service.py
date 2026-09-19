"""Grading service: AI scoring of an attempt with retries (fixes §4.9).

Key properties:
  - No DB transaction is held while calling the external AI provider.
  - Grading is idempotent per attempt: attempt.status controls re-entry.
  - Results are persisted per-answer plus an overall score in basis points.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import GradeItem, GradingContext, get_ai_provider
from app.core.errors import AIProviderError, NotFoundError
from app.core.logging import get_logger
from app.models.exam import (
    BP_SCALE,
    Exam,
    ExamAttempt,
    GradingJob,
    GradingResult,
    Question,
    StudentAnswer,
)

log = get_logger("grading")


class GradingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def enqueue(self, attempt: ExamAttempt) -> GradingJob:
        job = GradingJob(
            attempt_id=attempt.id,
            owner_id=attempt.user_id,
            kind="grading",
            status="queued",
        )
        self.session.add(job)
        return job

    async def enqueue_if_absent(self, attempt: ExamAttempt) -> GradingJob | None:
        """Idempotent enqueue: never create a second grading job for an attempt."""
        existing = (
            await self.session.execute(
                select(GradingJob).where(GradingJob.attempt_id == attempt.id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        return self.enqueue(attempt)

    async def grade_attempt(self, attempt: ExamAttempt) -> ExamAttempt:
        # Load answers + questions in one query (avoids N+1, §4.13). Only
        # questions that belong to this attempt's exam are considered.
        stmt = (
            select(StudentAnswer, Question)
            .join(Question, Question.id == StudentAnswer.question_id)
            .where(StudentAnswer.attempt_id == attempt.id)
            .where(Question.exam_id == attempt.exam_id)
            .order_by(Question.position)
        )
        rows = (await self.session.execute(stmt)).all()
        if not rows:
            raise NotFoundError("Attempt has no answers")

        items = [
            GradeItem(
                question=q.prompt,
                correct_answer=q.correct_answer or "",
                student_answer=sa.answer_text or "",
            )
            for sa, q in rows
        ]

        # Call the provider OUTSIDE any transaction to avoid long-held locks.
        provider = get_ai_provider()
        result = await provider.grade(GradingContext(items=items))

        total_score = 0
        for (sa, q), graded in zip(rows, result.items, strict=True):
            sa.score_bp = min(graded.score_bp, q.max_score_bp)
            sa.max_score_bp = q.max_score_bp
            sa.feedback = graded.feedback
            sa.similarity_bp = graded.similarity_bp
            sa.graded_at = datetime.now(UTC)
            total_score += sa.score_bp

        # The denominator MUST be the full max score of the exam, not only the
        # answered questions — otherwise skipping questions inflates the score.
        full_max = (
            await self.session.execute(
                select(func.coalesce(func.sum(Question.max_score_bp), 0)).where(
                    Question.exam_id == attempt.exam_id
                )
            )
        ).scalar_one()
        attempt.score_bp = int(round(total_score * BP_SCALE / full_max)) if full_max else 0
        exam = await self.session.get(Exam, attempt.exam_id)
        threshold = exam.passing_score_bp if exam else 6000
        attempt.passed = attempt.score_bp >= threshold
        attempt.graded_at = datetime.now(UTC)
        attempt.status = "graded"
        await self.session.flush()

        log.info(
            "attempt_graded",
            attempt_id=str(attempt.id),
            score_bp=attempt.score_bp,
            passed=attempt.passed,
        )
        return attempt

    async def record_job_result(
        self, job: GradingJob, attempt: ExamAttempt, provider_name: str
    ) -> None:
        self.session.add(
            GradingResult(
                job_id=job.id,
                attempt_id=attempt.id,
                model=provider_name,
                raw={"score_bp": attempt.score_bp, "passed": attempt.passed},
            )
        )


async def process_grading_job(session: AsyncSession, job_id: uuid.UUID) -> bool:
    """Worker entrypoint: grade an attempt with bounded retries."""
    job = await session.get(GradingJob, job_id)
    if job is None or job.status in ("done", "failed"):
        return False
    job.status = "running"
    job.started_at = datetime.now(UTC)
    job.attempts += 1
    await session.flush()

    attempt = await session.get(ExamAttempt, job.attempt_id) if job.attempt_id else None
    if attempt is None:
        job.status = "failed"
        job.error_code = "attempt_missing"
        job.error_message = "Attempt not found"
        await session.flush()
        return False

    try:
        service = GradingService(session)
        await service.grade_attempt(attempt)
        await service.record_job_result(job, attempt, "provider")
        job.status = "done"
        job.finished_at = datetime.now(UTC)
        job.error_code = None
        job.error_message = None
        await session.flush()
        return True
    except AIProviderError as exc:
        job.error_code = "ai_error"
        job.error_message = str(exc)
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            attempt.status = "grading_failed"
        else:
            # Exponential backoff, cap at 10 minutes.
            from datetime import timedelta

            delay = min(600, 2**job.attempts)
            job.status = "queued"
            job.available_at = datetime.now(UTC) + timedelta(seconds=delay)
        await session.flush()
        log.warning("grading_job_retry", job_id=str(job.id), attempts=job.attempts)
        return False
