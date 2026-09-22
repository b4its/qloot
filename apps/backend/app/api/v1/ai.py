"""AI job status + manual grading endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, TeacherUser
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db.session import transaction
from app.models.exam import Exam, ExamAttempt, GradingJob, Question
from app.schemas.material import AIJobOut, GradedItemOut, GradeRequest
from app.services.grading_service import GradingService

router = APIRouter()


async def _job_or_404(db, job_id: uuid.UUID) -> GradingJob:
    job = await db.get(GradingJob, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    return job


@router.get("/jobs/{job_id}", response_model=AIJobOut)
async def get_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession):
    job = await _job_or_404(db, job_id)
    if job.owner_id is not None and job.owner_id != user.id and not user.has_role("admin"):
        raise ForbiddenError("You do not own this job")
    return AIJobOut.model_validate(job)


@router.post("/questions/{question_id}/regenerate", response_model=AIJobOut)
async def regenerate_question(question_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        question = await db.get(Question, question_id)
        if question is None:
            raise NotFoundError("Question not found")
        if (
            question.owner_id is not None
            and question.owner_id != user.id
            and not user.has_role("admin")
        ):
            raise ForbiddenError("You do not own this question")
        if question.material_id is None:
            raise NotFoundError("Question has no source material")
        from app.services.material_service import MaterialService

        job = await MaterialService(db).enqueue_generation(
            question.material_id,
            user,
            count=1,
            language="id",
            exam_id=question.exam_id,
        )
    return AIJobOut.model_validate(job)


@router.post("/grade", response_model=list[GradedItemOut])
async def grade_attempt(payload: GradeRequest, user: CurrentUser, db: DbSession):
    """Synchronously grade an attempt (the worker also grades on submit).

    A student may only (re)trigger grading of their *own* attempt once it has
    been submitted — never while it is still ``in_progress`` (that would let a
    student stamp a final score before answering, and without ``submitted_at``,
    which breaks ranking). Teachers/admins may grade attempts on exams they own.
    """
    async with transaction(db):
        attempt = await db.get(ExamAttempt, payload.attempt_id)
        if attempt is None:
            raise NotFoundError("Attempt not found")
        if attempt.user_id != user.id:
            # A teacher may only grade attempts on exams they own (or an admin).
            if not user.has_role("admin") and not user.has_role("teacher"):
                raise ForbiddenError("You cannot grade this attempt")
            if not user.has_role("admin"):
                exam = await db.get(Exam, attempt.exam_id)
                if exam is None or exam.owner_id != user.id:
                    raise ForbiddenError("You do not own this exam")
        elif attempt.status not in ("submitted", "grading_failed"):
            raise ConflictError("Only a submitted attempt can be graded")
        await GradingService(db).grade_attempt(attempt)

    from sqlalchemy import select

    from app.models.exam import StudentAnswer

    rows = (
        (await db.execute(select(StudentAnswer).where(StudentAnswer.attempt_id == attempt.id)))
        .scalars()
        .all()
    )
    return [
        GradedItemOut(
            question_id=a.question_id,
            score_bp=a.score_bp,
            feedback=a.feedback,
            similarity_bp=a.similarity_bp,
        )
        for a in rows
    ]
