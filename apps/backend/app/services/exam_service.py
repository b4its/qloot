"""Exam service: exams, questions, attempts, answers.

Important correctness properties:
  - Ownership checks on every mutation (§4.2).
  - Autosave is idempotent via UNIQUE(attempt_id, question_id).
  - Submit is idempotent: re-submitting a graded attempt is a no-op.
  - submitted_at is server-authoritative (used for ranking).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.exam import Exam, ExamAttempt, Question, StudentAnswer
from app.models.identity import User

log = get_logger("exams")


class ExamService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- authorization helpers --------------------------------------------
    async def _get_owned_exam(self, exam_id: uuid.UUID, user: User) -> Exam:
        exam = await self.session.get(Exam, exam_id)
        if exam is None:
            raise NotFoundError("Exam not found")
        if not user.has_role("admin") and exam.owner_id != user.id:
            raise ForbiddenError("You do not own this exam")
        return exam

    # --- exams -------------------------------------------------------------
    async def create(self, owner: User, **data) -> Exam:
        exam = Exam(owner_id=owner.id, **data)
        self.session.add(exam)
        await self.session.flush()
        return exam

    async def get(self, exam_id: uuid.UUID) -> Exam:
        exam = await self.session.get(Exam, exam_id)
        if exam is None:
            raise NotFoundError("Exam not found")
        return exam

    async def list(self, user: User, *, limit: int = 50, offset: int = 0) -> list[Exam]:
        stmt = select(Exam).order_by(Exam.created_at.desc()).limit(limit).offset(offset)
        if not user.has_role("teacher", "admin"):
            stmt = stmt.where(Exam.is_active.is_(True))
        else:
            stmt = stmt.where(Exam.owner_id == user.id) if not user.has_role("admin") else stmt
        return list((await self.session.execute(stmt)).scalars().all())

    async def update(self, exam_id: uuid.UUID, user: User, **data) -> Exam:
        exam = await self._get_owned_exam(exam_id, user)
        for k, v in data.items():
            if v is not None:
                setattr(exam, k, v)
        await self.session.flush()
        return exam

    async def publish(self, exam_id: uuid.UUID, user: User) -> Exam:
        exam = await self._get_owned_exam(exam_id, user)
        exam.status = "published"
        exam.is_active = True
        await self.session.flush()
        return exam

    async def unpublish(self, exam_id: uuid.UUID, user: User) -> Exam:
        exam = await self._get_owned_exam(exam_id, user)
        exam.status = "closed"
        exam.is_active = False
        await self.session.flush()
        return exam

    # --- questions ---------------------------------------------------------
    async def add_question(self, exam_id: uuid.UUID, user: User, **data) -> Question:
        exam = await self._get_owned_exam(exam_id, user)
        question = Question(
            exam_id=exam.id, owner_id=user.id, source="manual", review_status="approved", **data
        )
        self.session.add(question)
        await self.session.flush()
        return question

    async def list_questions(self, exam_id: uuid.UUID) -> list[Question]:
        stmt = select(Question).where(Question.exam_id == exam_id).order_by(Question.position)
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_question(self, question_id: uuid.UUID, user: User, **data) -> Question:
        question = await self.session.get(Question, question_id)
        if question is None:
            raise NotFoundError("Question not found")
        if not user.has_role("admin") and question.owner_id != user.id:
            raise ForbiddenError("You do not own this question")
        for k, v in data.items():
            if v is not None:
                setattr(question, k, v)
        await self.session.flush()
        return question

    # --- attempts ----------------------------------------------------------
    async def start_attempt(self, exam_id: uuid.UUID, user: User) -> ExamAttempt:
        exam = await self.get(exam_id)
        if not exam.is_active:
            raise ConflictError("Exam is not open")
        # Lock the exam row to serialize concurrent attempt creation, then
        # compute the next attempt number. The UNIQUE(exam_id,user_id,num)
        # constraint is the ultimate guard against races.
        await self.session.execute(select(Exam.id).where(Exam.id == exam_id).with_for_update())
        max_num = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.max(ExamAttempt.attempt_number), 0)).where(
                        ExamAttempt.exam_id == exam_id, ExamAttempt.user_id == user.id
                    )
                )
            ).scalar_one()
        )
        attempt = ExamAttempt(
            exam_id=exam_id, user_id=user.id, attempt_number=max_num + 1, status="in_progress"
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def _get_own_attempt(self, attempt_id: uuid.UUID, user: User) -> ExamAttempt:
        attempt = await self.session.get(ExamAttempt, attempt_id)
        if attempt is None:
            raise NotFoundError("Attempt not found")
        # Students may only touch their own attempts; teachers/admins may view.
        if attempt.user_id != user.id and not user.has_role("teacher", "admin"):
            raise ForbiddenError("You cannot access this attempt")
        return attempt

    async def get_attempt(self, attempt_id: uuid.UUID, user: User) -> ExamAttempt:
        return await self._get_own_attempt(attempt_id, user)

    async def save_answer(
        self, attempt_id: uuid.UUID, question_id: uuid.UUID, user: User, answer_text: str
    ) -> StudentAnswer:
        attempt = await self._get_own_attempt(attempt_id, user)
        if attempt.user_id != user.id:
            raise ForbiddenError("You cannot answer this attempt")
        if attempt.status not in ("in_progress",):
            raise ConflictError("Attempt is not in progress")
        stmt = select(StudentAnswer).where(
            StudentAnswer.attempt_id == attempt_id, StudentAnswer.question_id == question_id
        )
        answer = (await self.session.execute(stmt)).scalar_one_or_none()
        if answer is None:
            answer = StudentAnswer(
                attempt_id=attempt_id, question_id=question_id, answer_text=answer_text
            )
            self.session.add(answer)
        else:
            answer.answer_text = answer_text
        await self.session.flush()
        return answer

    async def submit_attempt(self, attempt_id: uuid.UUID, user: User) -> ExamAttempt:
        attempt = await self._get_own_attempt(attempt_id, user)
        if attempt.user_id != user.id:
            raise ForbiddenError("You cannot submit this attempt")
        # Idempotent submit: if already submitted/graded, return as-is.
        if attempt.status in ("submitted", "graded", "grading_failed"):
            return attempt
        exam = await self.session.get(Exam, attempt.exam_id)
        now = datetime.now(UTC)
        if exam and exam.closes_at and now > exam.closes_at:
            raise ConflictError("The exam deadline has passed")
        attempt.submitted_at = now
        attempt.status = "submitted"
        if attempt.started_at:
            attempt.duration_seconds = int((now - attempt.started_at).total_seconds())
        await self.session.flush()
        log.info("attempt_submitted", attempt_id=str(attempt.id))
        return attempt

    async def list_answers(self, attempt_id: uuid.UUID) -> list[StudentAnswer]:
        stmt = select(StudentAnswer).where(StudentAnswer.attempt_id == attempt_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def my_attempts(self, user: User) -> list[ExamAttempt]:
        stmt = (
            select(ExamAttempt)
            .where(ExamAttempt.user_id == user.id)
            .order_by(ExamAttempt.started_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def exam_results(self, exam_id: uuid.UUID, user: User) -> list[ExamAttempt]:
        await self._get_owned_exam(exam_id, user)
        stmt = (
            select(ExamAttempt)
            .where(ExamAttempt.exam_id == exam_id)
            .order_by(ExamAttempt.score_bp.desc().nullslast())
        )
        return list((await self.session.execute(stmt)).scalars().all())
