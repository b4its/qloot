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
from app.core.errors import AIProviderError
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

    async def grade_mc_answers(self, attempt: ExamAttempt) -> int:
        """Deterministically score the multiple-choice questions of an attempt.

        MC answers need no AI: a correct option label earns the question's full
        ``max_score_bp``, anything else earns 0. Idempotent (re-runnable).
        Returns the number of MC answers scored.
        """
        stmt = (
            select(StudentAnswer, Question)
            .join(Question, Question.id == StudentAnswer.question_id)
            .where(StudentAnswer.attempt_id == attempt.id)
            .where(Question.exam_id == attempt.exam_id)
            .where(Question.qtype == "multiple_choice")
        )
        rows = (await self.session.execute(stmt)).all()
        for sa, q in rows:
            chosen = (sa.answer_text or "").strip().upper()
            correct = (q.correct_answer or "").strip().upper()
            sa.score_bp = q.max_score_bp if chosen and chosen == correct else 0
            sa.max_score_bp = q.max_score_bp
            sa.feedback = "Benar" if sa.score_bp else "Salah"
            sa.similarity_bp = None
            sa.graded_at = datetime.now(UTC)
        if rows:
            await self.session.flush()
        return len(rows)

    async def _finalize_score(self, attempt: ExamAttempt) -> None:
        """Recompute the attempt's overall score/status from its graded answers."""
        total_score = (
            await self.session.execute(
                select(func.coalesce(func.sum(StudentAnswer.score_bp), 0)).where(
                    StudentAnswer.attempt_id == attempt.id,
                    StudentAnswer.graded_at.is_not(None),
                )
            )
        ).scalar_one() or 0
        # Denominator is the full exam max (skipping questions must not inflate).
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
        await self._maybe_award_badges(attempt)

    async def _maybe_award_badges(self, attempt: ExamAttempt) -> None:
        """Flawless attempts earn the 'perfect exam' badge; MC aces get one too."""
        from app.models.identity import User
        from app.services.social_service import BadgeService

        owner = await self.session.get(User, attempt.user_id)
        if owner is None:
            return
        badges = BadgeService(self.session)
        if (attempt.score_bp or 0) >= BP_SCALE:
            await badges.award(
                user=owner,
                code="perfect_exam",
                meta={"attempt_id": str(attempt.id), "exam_id": str(attempt.exam_id)},
            )
        # "Quiz master": a flawless multiple-choice quiz (all MC answers correct).
        mc_total = (
            await self.session.execute(
                select(func.count())
                .select_from(StudentAnswer)
                .join(Question, Question.id == StudentAnswer.question_id)
                .where(StudentAnswer.attempt_id == attempt.id)
                .where(Question.qtype == "multiple_choice")
            )
        ).scalar_one()
        if mc_total:
            mc_correct = (
                await self.session.execute(
                    select(func.count())
                    .select_from(StudentAnswer)
                    .join(Question, Question.id == StudentAnswer.question_id)
                    .where(StudentAnswer.attempt_id == attempt.id)
                    .where(Question.qtype == "multiple_choice")
                    .where(StudentAnswer.score_bp == StudentAnswer.max_score_bp)
                )
            ).scalar_one()
            if mc_correct == mc_total:
                await badges.award(
                    user=owner,
                    code="quiz_master",
                    meta={"attempt_id": str(attempt.id), "exam_id": str(attempt.exam_id)},
                )

    async def grade_attempt(self, attempt: ExamAttempt) -> ExamAttempt:
        # 1) Score multiple-choice questions deterministically (instant, no AI).
        await self.grade_mc_answers(attempt)

        # Load the ESSAY answers + questions for AI grading (avoid N+1).
        stmt = (
            select(StudentAnswer, Question)
            .join(Question, Question.id == StudentAnswer.question_id)
            .where(StudentAnswer.attempt_id == attempt.id)
            .where(Question.exam_id == attempt.exam_id)
            .where(Question.qtype != "multiple_choice")
            .order_by(Question.position)
        )
        rows = (await self.session.execute(stmt)).all()

        # No essay answers -> the attempt is fully graded by the deterministic
        # pass; no AI provider call is needed.
        if not rows:
            if attempt.status not in ("graded",):
                await self._finalize_score(attempt)
                log.info("attempt_graded_mc_only", attempt_id=str(attempt.id))
            return attempt

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

        # Guard against a provider returning the wrong number of items: treat it
        # as a retryable provider error rather than crashing mid-write.
        if len(result.items) != len(rows):
            raise AIProviderError(
                f"Provider returned {len(result.items)} grades for {len(rows)} answers"
            )

        for (sa, q), graded in zip(rows, result.items, strict=False):
            sa.score_bp = min(graded.score_bp, q.max_score_bp)
            sa.max_score_bp = q.max_score_bp
            sa.feedback = graded.feedback
            sa.similarity_bp = graded.similarity_bp
            sa.graded_at = datetime.now(UTC)

        await self._finalize_score(attempt)
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
            job.finished_at = datetime.now(UTC)
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
    except Exception as exc:  # noqa: BLE001
        # Any other failure (bad data, unexpected provider output, DB error)
        # must still reach a terminal state — never leave the job stuck in
        # "running" where the claim query would never pick it up again.
        job.status = "failed"
        job.error_code = "internal_error"
        job.error_message = f"{type(exc).__name__}: {exc}"[:500]
        job.finished_at = datetime.now(UTC)
        attempt.status = "grading_failed"
        await session.flush()
        log.error("grading_job_failed", job_id=str(job.id), error=str(exc))
        return False
