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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import GradeItem, GradingContext, get_ai_provider
from app.core import metrics
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
from app.services.auto_grading import auto_feedback, score_auto_answer

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
        job = self.enqueue(attempt)
        await self.session.flush()
        await self._meter_grading_job(job, attempt)
        return job

    async def _meter_grading_job(self, job: GradingJob, attempt: ExamAttempt) -> None:
        """Charge 1 ORT (or a free slot) for grading an essay attempt.

        Only attempts with essay answers reach the AI provider; a pure
        multiple-choice attempt is graded deterministically with no AI call, so
        it is never charged.
        """
        from app.models.exam import Question, StudentAnswer

        has_essay = (
            await self.session.execute(
                select(func.count())
                .select_from(StudentAnswer)
                .join(Question, Question.id == StudentAnswer.question_id)
                .where(StudentAnswer.attempt_id == attempt.id)
                .where(Question.qtype == "essay")
            )
        ).scalar_one()
        if not has_essay:
            return
        from app.models.identity import User
        from app.services.ai_usage_service import AiUsageService

        owner = await self.session.get(User, attempt.user_id)
        if owner is None:
            return
        await AiUsageService(self.session).charge_job(user=owner, job_id=job.id)

    async def reopen_for_regrade(self, attempt: ExamAttempt) -> GradingJob | None:
        """Re-queue grading for a failed attempt (teacher/admin retry).

        A permanently ``grading_failed`` attempt otherwise has no path back:
        ``enqueue_if_absent`` would return the existing (failed) job unchanged.
        Here we reset that job to ``queued`` and clear its error so the worker
        picks it up again, and flip the attempt back to ``submitted``.
        """
        job = (
            await self.session.execute(
                select(GradingJob).where(GradingJob.attempt_id == attempt.id)
            )
        ).scalar_one_or_none()
        if job is None:
            job = self.enqueue(attempt)
            await self.session.flush()
            attempt.status = "submitted"
            await self._meter_grading_job(job, attempt)
            return job
        # Only a terminal/failed job is re-openable; a queued/running one is left
        # alone so we never double-grade.
        if job.status in ("done",):
            return job
        job.status = "queued"
        job.attempts = 0
        job.error_code = None
        job.error_message = None
        job.available_at = datetime.now(UTC)
        job.finished_at = None
        attempt.status = "submitted"
        await self.session.flush()
        return job

    async def grade_mc_answers(self, attempt: ExamAttempt) -> int:
        """Deterministically score every auto-graded answer of an attempt.

        Multiple-choice / true-false are all-or-nothing; multi-select, numeric,
        fill-blank, matching and ordering award deterministic partial credit.
        Idempotent (re-runnable). Returns the number of answers scored.
        """
        auto_types = (
            "multiple_choice",
            "true_false",
            "multi_select",
            "numeric",
            "fill_blank",
            "matching",
            "ordering",
        )
        stmt = (
            select(StudentAnswer, Question)
            .join(Question, Question.id == StudentAnswer.question_id)
            .where(StudentAnswer.attempt_id == attempt.id)
            .where(Question.exam_id == attempt.exam_id)
            .where(Question.qtype.in_(auto_types))
        )
        rows = (await self.session.execute(stmt)).all()
        for sa, q in rows:
            ratio = score_auto_answer(q, sa.answer_text)
            sa.score_bp = int(round(q.max_score_bp * ratio))
            sa.max_score_bp = q.max_score_bp
            sa.feedback = auto_feedback(q, sa.answer_text, ratio)
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
        # Late-submission penalty: a submit after the attempt's deadline (but
        # inside the grace window) loses `late_penalty_bp` basis points.
        if (
            exam is not None
            and exam.late_penalty_bp > 0
            and attempt.expires_at is not None
            and attempt.submitted_at is not None
            and attempt.submitted_at > attempt.expires_at
        ):
            factor = max(0, BP_SCALE - exam.late_penalty_bp)
            attempt.score_bp = attempt.score_bp * factor // BP_SCALE
        threshold = exam.passing_score_bp if exam else 6000
        attempt.passed = attempt.score_bp >= threshold
        attempt.graded_at = datetime.now(UTC)
        attempt.status = "graded"
        await self.session.flush()
        await self._maybe_award_badges(attempt)
        await self._notify_graded(attempt, exam)

    async def override_answer(
        self,
        *,
        attempt: ExamAttempt,
        question_id: uuid.UUID,
        score_bp: int,
        feedback: str | None,
    ) -> StudentAnswer:
        """Teacher/admin manual score override for one answer.

        Sets the answer's score (clamped to the question's max), recomputes the
        attempt total/status, and — if the attempt is no longer flawless —
        reverses the idempotent "perfect exam" reward that C08 paid. Audited by
        the caller.
        """
        answer = (
            await self.session.execute(
                select(StudentAnswer).where(
                    StudentAnswer.attempt_id == attempt.id,
                    StudentAnswer.question_id == question_id,
                )
            )
        ).scalar_one_or_none()
        if answer is None:
            raise NotFoundError("Answer not found for this attempt")
        question = await self.session.get(Question, question_id)
        max_bp = question.max_score_bp if question else BP_SCALE
        answer.score_bp = max(0, min(int(score_bp), max_bp))
        answer.max_score_bp = max_bp
        answer.feedback = feedback if feedback is not None else answer.feedback
        answer.graded_at = datetime.now(UTC)
        await self.session.flush()

        # Recompute the attempt total using the same denominator as grading.
        await self._finalize_score(attempt)

        # If the perfect-exam reward was paid but the attempt is no longer
        # perfect, reverse it (idempotent on the deterministic reward key).
        if (attempt.score_bp or 0) < BP_SCALE:
            await self._revoke_perfect_exam_reward(attempt)
        return answer

    async def _revoke_perfect_exam_reward(self, attempt: ExamAttempt) -> None:
        from app.models.wallet import RewardAllocation
        from app.services.keys import exam_reward_key
        from app.services.reward_engine import RewardEngine

        rkey = exam_reward_key(attempt.id, "perfect_exam")
        allocation = (
            await self.session.execute(
                select(RewardAllocation).where(RewardAllocation.reward_key == rkey)
            )
        ).scalar_one_or_none()
        if allocation is None or allocation.status == "cancelled":
            return
        # Only compensate a reward that was actually credited off-chain.
        if allocation.status in ("pending", "confirmed", "failed"):
            await RewardEngine(self.session).refund_reward(
                user_id=allocation.user_id,
                amount=allocation.amount,
                allocation_id=allocation.id,
            )
        allocation.status = "cancelled"
        allocation.error_message = "Exam score overridden by a teacher"
        await self.session.flush()

    async def _notify_graded(self, attempt: ExamAttempt, exam: Exam | None) -> None:
        """Tell the student their exam was graded (best-effort)."""
        if attempt.user_id is None:
            return
        from app.services.social_service import NotificationService

        title = exam.title if exam is not None else "Ujian"
        pct = round((attempt.score_bp or 0) / 100)
        status = "lulus" if attempt.passed else "belum lulus"
        try:
            await NotificationService(self.session).notify(
                user_id=attempt.user_id,
                kind="reward",
                title=f"Nilai ujian keluar: {pct}%",
                body=f"{title} — {status}.",
                data={"exam_id": str(attempt.exam_id), "attempt_id": str(attempt.id)},
            )
        except Exception as exc:  # noqa: BLE001 - never block grading on notify
            log.warning("grading_notify_failed", error=str(exc))

    async def _maybe_award_badges(self, attempt: ExamAttempt) -> None:
        """Flawless attempts earn the 'perfect exam' badge; MC aces get one too."""
        from app.core.config import settings
        from app.models.identity import User
        from app.services.keys import exam_reward_key
        from app.services.reward_engine import RewardEngine
        from app.services.social_service import BadgeService

        owner = await self.session.get(User, attempt.user_id)
        if owner is None:
            return
        badges = BadgeService(self.session)
        rewards = RewardEngine(self.session)
        if (attempt.score_bp or 0) >= BP_SCALE:
            await badges.award(
                user=owner,
                code="perfect_exam",
                meta={"attempt_id": str(attempt.id), "exam_id": str(attempt.exam_id)},
            )
            # README: a perfect exam pays OPT (idempotent per attempt).
            await rewards.allocate_event_reward(
                user=owner,
                amount=settings.reward_perfect_exam,
                reward_type="perfect_exam",
                rkey=exam_reward_key(attempt.id, "perfect_exam"),
                description="Perfect exam reward",
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
                await rewards.allocate_event_reward(
                    user=owner,
                    amount=settings.reward_quiz_master,
                    reward_type="quiz_master",
                    rkey=exam_reward_key(attempt.id, "quiz_master"),
                    description="Quiz Master reward",
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
            .where(Question.qtype == "essay")
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
        metrics.incr("ai_jobs_total", kind="grading")

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
        # Idempotent: UNIQUE(job_id) guarantees one result per job, so a re-run
        # (e.g. after a reaper requeue) must not raise. SAVEPOINT keeps the rest
        # of the transaction intact if the row already exists.
        try:
            async with self.session.begin_nested():
                self.session.add(
                    GradingResult(
                        job_id=job.id,
                        attempt_id=attempt.id,
                        model=provider_name,
                        raw={"score_bp": attempt.score_bp, "passed": attempt.passed},
                    )
                )
                await self.session.flush()
        except IntegrityError:
            return


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
        metrics.incr("grading_failures_total", reason="attempt_missing")
        return False

    try:
        service = GradingService(session)
        await service.grade_attempt(attempt)
        from app.ai.provider import provider_name

        await service.record_job_result(job, attempt, provider_name())
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
            from app.services.ai_usage_service import AiUsageService

            await AiUsageService(session).refund_job(
                user_id=attempt.user_id, job_id=job.id
            )
            metrics.incr("grading_failures_total", reason="ai_error")
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
        from app.services.ai_usage_service import AiUsageService

        await AiUsageService(session).refund_job(user_id=attempt.user_id, job_id=job.id)
        await session.flush()
        metrics.incr("grading_failures_total", reason="internal_error")
        log.error("grading_job_failed", job_id=str(job.id), error=str(exc))
        return False
