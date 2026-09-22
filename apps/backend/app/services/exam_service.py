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

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.exam import Exam, ExamAttempt, Question, QuestionOption, StudentAnswer
from app.models.identity import User

log = get_logger("exams")

_OPTION_LABELS = "ABCDEFGH"


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

    @staticmethod
    def ensure_visible(exam: Exam, user: User) -> None:
        """Enforce read visibility for a single exam.

        Admins see anything; a teacher sees their own exams (incl. drafts) and
        any active exam; everyone else (students) sees only active exams.
        """
        if user.has_role("admin"):
            return
        if exam.owner_id == user.id:
            return
        if user.has_role("teacher"):
            if exam.is_active:
                return
            raise ForbiddenError("You do not own this exam")
        if not exam.is_active:
            raise NotFoundError("Exam not found")

    async def list_all(self, user: User, *, limit: int = 50, offset: int = 0) -> list[Exam]:
        stmt = select(Exam).order_by(Exam.created_at.desc()).limit(limit).offset(offset)
        if not user.has_role("teacher", "admin"):
            stmt = stmt.where(Exam.is_active.is_(True))
        else:
            stmt = stmt.where(Exam.owner_id == user.id) if not user.has_role("admin") else stmt
        return list((await self.session.execute(stmt)).scalars().all())

    async def question_counts(
        self, exam_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[int, int, int]]:
        """Batched (total, multiple_choice, essay) question counts per exam.

        One grouped query for every exam id (never N+1).
        """
        if not exam_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Question.exam_id, Question.qtype, func.count())
                .where(Question.exam_id.in_(exam_ids))
                .group_by(Question.exam_id, Question.qtype)
            )
        ).all()
        counts: dict[uuid.UUID, tuple[int, int, int]] = {}
        for exam_id, qtype, n in rows:
            total, mc, essay = counts.get(exam_id, (0, 0, 0))
            if qtype == "multiple_choice":
                mc += int(n)
            else:
                essay += int(n)
            counts[exam_id] = (total + int(n), mc, essay)
        return counts

    async def list_all_with_counts(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> list[tuple[Exam, int, int, int]]:
        """Exams plus their (total, mc, essay) question counts (batched)."""
        exams = await self.list_all(user, limit=limit, offset=offset)
        counts = await self.question_counts([e.id for e in exams])
        return [(e, *counts.get(e.id, (0, 0, 0))) for e in exams]

    async def update(self, exam_id: uuid.UUID, user: User, **data) -> Exam:
        exam = await self._get_owned_exam(exam_id, user)
        for k, v in data.items():
            if v is not None:
                setattr(exam, k, v)
        await self.session.flush()
        return exam

    async def publish(self, exam_id: uuid.UUID, user: User) -> Exam:
        exam = await self._get_owned_exam(exam_id, user)
        # AI-generated questions start as ``pending`` and must be reviewed before
        # students can be graded on them; publishing an exam with unreviewed or
        # rejected questions would silently expose unreviewed content.
        unreviewed = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(Question)
                    .where(Question.exam_id == exam_id, Question.review_status != "approved")
                )
            ).scalar_one()
        )
        if unreviewed:
            raise ConflictError(
                f"{unreviewed} soal belum ditinjau/disetujui — tinjau soal sebelum menerbitkan"
            )
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
    async def add_question(
        self, exam_id: uuid.UUID, user: User, *, options: list[dict] | None = None, **data
    ) -> Question:
        exam = await self._get_owned_exam(exam_id, user)
        qtype = data.get("qtype", "essay")
        if qtype == "multiple_choice" and not options:
            raise ValidationError("multiple_choice requires options")
        question = Question(
            exam_id=exam.id, owner_id=user.id, source="manual", review_status="approved", **data
        )
        self.session.add(question)
        await self.session.flush()
        if qtype == "multiple_choice":
            await self._replace_options(question, options or [])
        return question

    async def list_questions(self, exam_id: uuid.UUID) -> list[Question]:
        stmt = select(Question).where(Question.exam_id == exam_id).order_by(Question.position)
        return list((await self.session.execute(stmt)).scalars().all())

    async def exam_has_essay(self, exam_id: uuid.UUID) -> bool:
        """True if the exam has any AI-graded (essay) question."""
        count = (
            await self.session.execute(
                select(func.count())
                .select_from(Question)
                .where(Question.exam_id == exam_id, Question.qtype != "multiple_choice")
            )
        ).scalar_one()
        return int(count) > 0

    async def options_for(self, question_id: uuid.UUID) -> list[QuestionOption]:
        stmt = (
            select(QuestionOption)
            .where(QuestionOption.question_id == question_id)
            .order_by(QuestionOption.position)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _replace_options(self, question: Question, options: list[dict]) -> None:
        """Replace a question's options wholesale (atomic: delete + insert)."""
        if len(options) < 2:
            raise ValidationError("multiple_choice needs at least 2 options")
        correct = [o for o in options if o.get("is_correct")]
        if len(correct) != 1:
            raise ValidationError("multiple_choice needs exactly one correct option")
        # Drop existing options, then insert the new set deterministically.
        for existing in await self.options_for(question.id):
            await self.session.delete(existing)
        await self.session.flush()
        correct_label = ""
        for i, opt in enumerate(options):
            label = (opt.get("label") or _OPTION_LABELS[i]).strip().upper()[:8]
            self.session.add(
                QuestionOption(
                    question_id=question.id,
                    label=label,
                    text=opt["text"],
                    is_correct=bool(opt.get("is_correct")),
                    position=i,
                )
            )
            if opt.get("is_correct"):
                correct_label = label
        # Keep ``correct_answer`` in sync with the correct option's label so
        # existing tooling/reporting still has a single answer key.
        question.correct_answer = correct_label
        await self.session.flush()

    async def update_question(
        self, question_id: uuid.UUID, user: User, *, options: list[dict] | None = None, **data
    ) -> Question:
        question = await self.session.get(Question, question_id)
        if question is None:
            raise NotFoundError("Question not found")
        if not user.has_role("admin") and question.owner_id != user.id:
            raise ForbiddenError("You do not own this question")
        for k, v in data.items():
            if v is not None:
                setattr(question, k, v)
        if question.qtype == "multiple_choice" and options is not None:
            await self._replace_options(question, options)
        await self.session.flush()
        return question

    async def delete_question(self, question_id: uuid.UUID, user: User) -> None:
        question = await self.session.get(Question, question_id)
        if question is None:
            raise NotFoundError("Question not found")
        if not user.has_role("admin") and question.owner_id != user.id:
            raise ForbiddenError("You do not own this question")
        # Refuse while a submitted/graded attempt references the question, so we
        # never orphan student answers or corrupt a score denominator.
        referenced = (
            await self.session.execute(
                select(func.count())
                .select_from(StudentAnswer)
                .where(StudentAnswer.question_id == question_id)
            )
        ).scalar_one()
        if referenced:
            raise ConflictError("Cannot delete a question that already has answers")
        await self.session.delete(question)
        await self.session.flush()

    async def delete(self, exam_id: uuid.UUID, user: User) -> None:
        exam = await self._get_owned_exam(exam_id, user)
        # Refuse once anyone has attempted it — deleting would orphan attempts
        # and their answers/scores.
        attempts = (
            await self.session.execute(
                select(func.count()).select_from(ExamAttempt).where(ExamAttempt.exam_id == exam_id)
            )
        ).scalar_one()
        if attempts:
            raise ConflictError("Cannot delete an exam that has attempts")
        await self.session.delete(exam)
        await self.session.flush()

    # --- attempts ----------------------------------------------------------
    async def start_attempt(self, exam_id: uuid.UUID, user: User) -> ExamAttempt:
        exam = await self.get(exam_id)
        if not exam.is_active:
            raise ConflictError("Exam is not open")
        # Enforce the scheduling window (when the teacher set one).
        now = datetime.now(UTC)
        if exam.opens_at and now < exam.opens_at:
            raise ConflictError("Ujian belum dibuka")
        if exam.closes_at and now > exam.closes_at:
            raise ConflictError("Batas waktu ujian telah lewat")
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
        # The question must belong to the attempt's exam; otherwise a student
        # could inject answers for questions from other exams and skew grading.
        question = await self.session.get(Question, question_id)
        if question is None or question.exam_id != attempt.exam_id:
            raise NotFoundError("Question not found in this exam")
        if question.qtype == "multiple_choice":
            # The answer must be one of the question's option labels.
            labels = {o.label for o in await self.options_for(question_id)}
            choice = (answer_text or "").strip().upper()
            if choice and choice not in labels:
                raise ValidationError("Answer must be one of the question's options")
            answer_text = choice
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

    async def my_attempts(
        self, user: User, *, limit: int = 100, offset: int = 0
    ) -> list[ExamAttempt]:
        stmt = (
            select(ExamAttempt)
            .where(ExamAttempt.user_id == user.id)
            .order_by(ExamAttempt.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def exam_results(
        self, exam_id: uuid.UUID, user: User, *, limit: int = 200, offset: int = 0
    ) -> list[tuple[ExamAttempt, str | None]]:
        """Return (attempt, student_name) pairs for an exam, best score first."""
        await self._get_owned_exam(exam_id, user)
        stmt = (
            select(ExamAttempt, User.full_name)
            .join(User, User.id == ExamAttempt.user_id)
            .where(ExamAttempt.exam_id == exam_id)
            .order_by(ExamAttempt.score_bp.desc().nullslast())
            .limit(limit)
            .offset(offset)
        )
        return [(a, name) for a, name in (await self.session.execute(stmt)).all()]

    async def exam_review(
        self, exam_id: uuid.UUID, user: User, *, limit: int = 200, offset: int = 0
    ) -> tuple[Exam, list[tuple[ExamAttempt, str | None, dict[uuid.UUID, dict]]]]:
        """Per-student answer review for an exam (owner/admin only).

        For every attempt it returns the student's name plus a map of
        ``question_id -> {answer row, is_correct, displays}`` built from a
        handful of batched queries (never N+1). Used by the teacher results
        review: who took the exam, which questions they answered, and whether
        each answer was correct.
        """
        exam = await self._get_owned_exam(exam_id, user)
        attempts = await self.exam_results(exam_id, user, limit=limit, offset=offset)
        attempt_ids = [a.id for a, _ in attempts]
        if not attempt_ids:
            return exam, []

        # One query for every answer across the page of attempts.
        answer_rows = list(
            (
                await self.session.execute(
                    select(StudentAnswer).where(StudentAnswer.attempt_id.in_(attempt_ids))
                )
            )
            .scalars()
            .all()
        )
        # One query for the exam's questions, and one for all their options.
        questions = {q.id: q for q in await self.list_questions(exam_id)}
        option_map: dict[tuple[uuid.UUID, str], str] = {}
        if questions:
            opt_rows = (
                await self.session.execute(
                    select(
                        QuestionOption.question_id, QuestionOption.label, QuestionOption.text
                    ).where(QuestionOption.question_id.in_(list(questions.keys())))
                )
            ).all()
            option_map = {(qid, label): text for qid, label, text in opt_rows}

        # Group answers by attempt, then assemble the review map per attempt.
        by_attempt: dict[uuid.UUID, list[StudentAnswer]] = {aid: [] for aid in attempt_ids}
        for sa in answer_rows:
            by_attempt.setdefault(sa.attempt_id, []).append(sa)

        def _review_for(sa: StudentAnswer) -> dict:
            q = questions.get(sa.question_id)
            is_mc = bool(q and q.qtype == "multiple_choice")
            chosen = (sa.answer_text or "").strip().upper()
            correct_label = (q.correct_answer or "").strip().upper() if q else ""
            # MC correctness is only known once the answer has been graded.
            is_correct: bool | None = None
            if is_mc and sa.score_bp is not None:
                is_correct = sa.score_bp >= sa.max_score_bp and sa.max_score_bp > 0
            return {
                "question_id": sa.question_id,
                "position": q.position if q else 0,
                "qtype": q.qtype if q else "essay",
                "prompt": q.prompt if q else "",
                "answer_text": sa.answer_text,
                "answer_display": (
                    option_map.get((sa.question_id, chosen)) if is_mc else sa.answer_text
                ),
                "correct_answer": correct_label if is_mc else None,
                "correct_display": (
                    option_map.get((sa.question_id, correct_label)) if is_mc else None
                ),
                "is_correct": is_correct,
                "score_bp": sa.score_bp,
                "max_score_bp": sa.max_score_bp,
                "feedback": sa.feedback,
            }

        out: list[tuple[ExamAttempt, str | None, dict[uuid.UUID, dict]]] = []
        for attempt, name in attempts:
            review: dict[uuid.UUID, dict] = {}

            def _pos(s: StudentAnswer) -> int:
                q = questions.get(s.question_id)
                return q.position if q else 0

            for sa in sorted(by_attempt.get(attempt.id, []), key=_pos):
                review[sa.question_id] = _review_for(sa)
            out.append((attempt, name, review))
        return exam, out
