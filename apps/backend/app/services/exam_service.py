"""Exam service: exams, questions, attempts, answers.

Important correctness properties:
  - Ownership checks on every mutation (§4.2).
  - Autosave is idempotent via UNIQUE(attempt_id, question_id).
  - Submit is idempotent: re-submitting a graded attempt is a no-op.
  - submitted_at is server-authoritative (used for ranking).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.exam import Exam, ExamAttempt, Question, QuestionOption, StudentAnswer
from app.models.identity import User

log = get_logger("exams")

_OPTION_LABELS = "ABCDEFGH"


def _point_biserial(xs: list[float], ys: list[float]) -> float:
    """Point-biserial / Pearson correlation; 0.0 when undefined.

    Used as the item-discrimination index: how strongly a question's score
    ratio correlates with the overall attempt score. Deterministic (no AI).
    """
    n = len(xs)
    if n < 2 or len(ys) != n:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return 0.0
    return cov / (vx**0.5 * vy**0.5)


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
            total, auto, essay = counts.get(exam_id, (0, 0, 0))
            if qtype == "essay":
                essay += int(n)
            else:
                auto += int(n)
            counts[exam_id] = (total + int(n), auto, essay)
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
        if qtype in ("multiple_choice", "multi_select") and not options:
            raise ValidationError(f"{qtype} requires options")
        question = Question(
            exam_id=exam.id, owner_id=user.id, source="manual", review_status="approved", **data
        )
        self.session.add(question)
        await self.session.flush()
        if qtype in ("multiple_choice", "multi_select"):
            await self._replace_options(question, options or [], multi=(qtype == "multi_select"))
        return question

    async def list_questions(self, exam_id: uuid.UUID) -> list[Question]:
        stmt = select(Question).where(Question.exam_id == exam_id).order_by(Question.position)
        return list((await self.session.execute(stmt)).scalars().all())

    async def reorder_questions(
        self, exam_id: uuid.UUID, user: User, question_ids: list[uuid.UUID]
    ) -> list[Question]:
        """Rewrite question positions atomically from the given order.

        Rejects an order that does not exactly cover the exam's questions.
        """
        await self._get_owned_exam(exam_id, user)
        questions = {q.id: q for q in await self.list_questions(exam_id)}
        if set(question_ids) != set(questions) or len(question_ids) != len(questions):
            raise ValidationError(
                "Reorder must list every question of the exam exactly once"
            )
        for i, qid in enumerate(question_ids):
            questions[qid].position = i
        await self.session.flush()
        return [questions[qid] for qid in question_ids]

    async def exam_has_essay(self, exam_id: uuid.UUID) -> bool:
        """True if the exam has any AI-graded (essay) question."""
        count = (
            await self.session.execute(
                select(func.count())
                .select_from(Question)
                .where(Question.exam_id == exam_id, Question.qtype == "essay")
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

    async def attempt_questions(
        self, attempt_id: uuid.UUID, user: User
    ) -> list[tuple[Question, list[QuestionOption]]]:
        """Questions + options for a specific attempt, deterministically shuffled.

        The shuffle seed is the attempt id, so re-loading the same attempt yields
        the same order (no jitter), while two different attempts see different
        orders. Option **labels stay canonical**, so grading (which compares the
        submitted label to the question's correct_answer) is unaffected.
        """
        import random

        attempt = await self._get_own_attempt(attempt_id, user)
        if attempt.user_id != user.id and not user.has_role("teacher", "admin"):
            raise ForbiddenError("You cannot access this attempt")
        exam = await self.session.get(Exam, attempt.exam_id)
        questions = await self.list_questions(attempt.exam_id)
        rows: list[tuple[Question, list[QuestionOption]]] = []
        for q in questions:
            opts = await self.options_for(q.id)
            if exam is not None and exam.shuffle_options and len(opts) > 1:
                rng = random.Random(f"{attempt.id}:opt:{q.id}")
                opts = opts[:]
                rng.shuffle(opts)
            rows.append((q, opts))
        if exam is not None and exam.shuffle_questions and len(rows) > 1:
            rng = random.Random(f"{attempt.id}:q")
            rng.shuffle(rows)
        return rows

    async def _replace_options(
        self, question: Question, options: list[dict], *, multi: bool = False
    ) -> None:
        """Replace a question's options wholesale (atomic: delete + insert)."""
        if len(options) < 2:
            raise ValidationError("multiple_choice needs at least 2 options")
        correct = [o for o in options if o.get("is_correct")]
        if multi:
            if len(correct) < 2:
                raise ValidationError("multi_select needs at least two correct options")
        elif len(correct) != 1:
            raise ValidationError("multiple_choice needs exactly one correct option")
        # Drop existing options, then insert the new set deterministically.
        for existing in await self.options_for(question.id):
            await self.session.delete(existing)
        await self.session.flush()
        correct_labels: list[str] = []
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
                correct_labels.append(label)
        if multi:
            # multi_select keys live in answer_json; correct_answer stays empty.
            question.correct_answer = None
            question.answer_json = {"correct": correct_labels}
        else:
            # Keep ``correct_answer`` in sync with the correct option's label so
            # existing tooling/reporting still has a single answer key.
            question.correct_answer = correct_labels[0] if correct_labels else ""
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
        if question.qtype in ("multiple_choice", "multi_select") and options is not None:
            await self._replace_options(
                question, options, multi=(question.qtype == "multi_select")
            )
        await self.session.flush()
        return question

    async def list_question_bank(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> list[Question]:
        """Every question a teacher owns, regardless of which exam it is on.

        This is the "question bank": questions can be listed and re-attached to
        other exams. Admins see all questions.
        """
        stmt = select(Question).order_by(Question.created_at.desc())
        if not user.has_role("admin"):
            stmt = stmt.where(Question.owner_id == user.id)
        stmt = stmt.limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def attach_question(
        self, target_exam_id: uuid.UUID, question_id: uuid.UUID, user: User
    ) -> Question:
        """Attach (or copy) an existing bank question into an exam.

        Copying — rather than moving — keeps the original intact so deleting the
        target exam never removes the bank question. Ownership is enforced for
        both the source question and the target exam.
        """
        exam = await self._get_owned_exam(target_exam_id, user)
        source = await self.session.get(Question, question_id)
        if source is None:
            raise NotFoundError("Question not found")
        if not user.has_role("admin") and source.owner_id != user.id:
            raise ForbiddenError("You do not own this question")
        # Next position within the target exam.
        next_pos = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.max(Question.position), -1)).where(
                        Question.exam_id == exam.id
                    )
                )
            ).scalar_one()
        ) + 1
        clone = Question(
            exam_id=exam.id,
            material_id=source.material_id,
            owner_id=user.id,
            prompt=source.prompt,
            correct_answer=source.correct_answer,
            qtype=source.qtype,
            max_score_bp=source.max_score_bp,
            position=next_pos,
            source="bank",
            review_status="approved",
            answer_json=source.answer_json,
        )
        self.session.add(clone)
        await self.session.flush()
        # Clone options for choice-based types.
        if source.qtype in ("multiple_choice", "multi_select"):
            for opt in await self.options_for(source.id):
                self.session.add(
                    QuestionOption(
                        question_id=clone.id,
                        label=opt.label,
                        text=opt.text,
                        is_correct=opt.is_correct,
                        position=opt.position,
                    )
                )
            await self.session.flush()
        return clone

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
        # Enforce the retake policy: 0 means unlimited.
        if exam.max_attempts and max_num >= exam.max_attempts:
            raise ConflictError(
                f"Batas percobaan tercapai ({exam.max_attempts}). "
                "Hubungi pengajar untuk percobaan tambahan."
            )
        attempt = ExamAttempt(
            exam_id=exam_id, user_id=user.id, attempt_number=max_num + 1, status="in_progress"
        )
        # Server-authoritative deadline: the attempt's own duration, never later
        # than the exam's close time. The client cannot extend this.
        expires_at = now + timedelta(minutes=exam.duration_minutes or 60)
        if exam.closes_at is not None and exam.closes_at < expires_at:
            expires_at = exam.closes_at
        attempt.expires_at = expires_at
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    def _ensure_not_expired(self, attempt: ExamAttempt, now: datetime) -> None:
        """Refuse writes to an in-progress attempt past its server deadline."""
        if (
            attempt.status == "in_progress"
            and attempt.expires_at is not None
            and now > attempt.expires_at
        ):
            raise ConflictError("Waktu ujian telah habis")

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
        self._ensure_not_expired(attempt, datetime.now(UTC))
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
        elif question.qtype == "true_false":
            choice = (answer_text or "").strip().lower()
            if choice and choice not in ("true", "false"):
                raise ValidationError("Answer must be 'true' or 'false'")
            answer_text = choice
        elif question.qtype == "multi_select":
            # The answer is a JSON array of option labels.
            labels = {o.label for o in await self.options_for(question_id)}
            import json as _json

            try:
                raw = _json.loads(answer_text) if answer_text else []
            except (ValueError, TypeError):
                raise ValidationError("multi_select answer must be a JSON array") from None
            if not isinstance(raw, list):
                raise ValidationError("multi_select answer must be a JSON array")
            picked = [str(x).strip().upper() for x in raw if str(x).strip()]
            if any(p not in labels for p in picked):
                raise ValidationError("Answer contains an unknown option")
            answer_text = _json.dumps(sorted(set(picked)))
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
        # Server-side deadline. A submit after the deadline is rejected unless it
        # falls inside the configured grace window (late penalty then applies at
        # grading). The sweeper auto-submits truly expired attempts.
        if (
            attempt.status == "in_progress"
            and attempt.expires_at is not None
            and now > attempt.expires_at
        ):
            grace = exam.grace_seconds if exam else 0
            if now > attempt.expires_at + timedelta(seconds=grace):
                raise ConflictError("Waktu ujian telah habis")
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

    # Violation kinds that contribute to flagging an attempt.
    _VIOLATION_KINDS = frozenset({"blur", "visibility_hidden", "paste"})
    # How many violations before an attempt is flagged.
    FLAG_THRESHOLD = 5

    async def record_events(
        self, attempt_id: uuid.UUID, user: User, events: list[dict]
    ) -> int:
        """Persist proctoring telemetry for an attempt.

        Best-effort: never raises on weird input and never blocks a submit. After
        recording, re-counts the attempt's violation events and flags it once the
        threshold is crossed (``is_flagged`` / ``flag_reason``).
        """
        attempt = await self._get_own_attempt(attempt_id, user)
        if attempt.user_id != user.id:
            raise ForbiddenError("You cannot report events for this attempt")
        from app.models.exam import AttemptEvent

        saved = 0
        for ev in events[:50]:
            kind = str(ev.get("kind", ""))[:32]
            if not kind:
                continue
            qid = ev.get("question_id")
            try:
                question_uuid = uuid.UUID(str(qid)) if qid else None
            except (ValueError, TypeError):
                question_uuid = None
            self.session.add(
                AttemptEvent(
                    attempt_id=attempt.id,
                    kind=kind,
                    question_id=question_uuid,
                    detail=ev.get("detail") if isinstance(ev.get("detail"), dict) else None,
                )
            )
            saved += 1
        await self.session.flush()

        # Flag the attempt once enough violations accumulate.
        violations = (
            await self.session.execute(
                select(func.count())
                .select_from(AttemptEvent)
                .where(
                    AttemptEvent.attempt_id == attempt.id,
                    AttemptEvent.kind.in_(self._VIOLATION_KINDS),
                )
            )
        ).scalar_one()
        if int(violations) >= self.FLAG_THRESHOLD and not attempt.is_flagged:
            attempt.is_flagged = True
            attempt.flag_reason = (
                f"{int(violations)} proctoring violations (tab switch / focus loss)"
            )
            await self.session.flush()
        return saved

    async def analytics_report(self, exam_id: uuid.UUID, user: User) -> dict:
        """Score distribution, per-question difficulty and discrimination.

        - histogram of attempt scores in 10% buckets;
        - difficulty (p-value) = mean score ratio per question;
        - discrimination = point-biserial correlation of a question's score
          ratio against the attempt total (deterministic, no AI).
        """
        await self._get_owned_exam(exam_id, user)
        attempts = (
            await self.session.execute(
                select(ExamAttempt).where(
                    ExamAttempt.exam_id == exam_id,
                    ExamAttempt.score_bp.is_not(None),
                )
            )
        ).scalars().all()
        scores = [int(a.score_bp or 0) for a in attempts]
        n = len(scores)

        histogram = [0] * 10
        for s in scores:
            histogram[min(9, max(0, s // 1000))] += 1

        questions = await self.list_questions(exam_id)
        qstats: list[dict] = []
        if n and questions:
            answer_rows = (
                await self.session.execute(
                    select(StudentAnswer).where(
                        StudentAnswer.attempt_id.in_([a.id for a in attempts])
                    )
                )
            ).scalars().all()
            by_q: dict[uuid.UUID, dict[uuid.UUID, float]] = {}
            total_by_attempt = {a.id: int(a.score_bp or 0) for a in attempts}
            for sa in answer_rows:
                if sa.graded_at is None or not sa.max_score_bp:
                    continue
                ratio = (sa.score_bp or 0) / sa.max_score_bp
                by_q.setdefault(sa.question_id, {})[sa.attempt_id] = ratio

            for q in questions:
                ratios = by_q.get(q.id, {})
                answered = len(ratios)
                if answered == 0:
                    qstats.append(
                        {
                            "question_id": str(q.id),
                            "prompt": q.prompt,
                            "qtype": q.qtype,
                            "answered": 0,
                            "difficulty_bp": None,
                            "discrimination": None,
                        }
                    )
                    continue
                p = sum(ratios.values()) / answered
                xs = [float(v) for v in ratios.values()]
                ys = [float(total_by_attempt[a_id]) for a_id in ratios]
                disc = _point_biserial(xs, ys)
                qstats.append(
                    {
                        "question_id": str(q.id),
                        "prompt": q.prompt,
                        "qtype": q.qtype,
                        "answered": answered,
                        "difficulty_bp": int(round(p * 10_000)),
                        "discrimination": round(disc, 3),
                    }
                )

        mean = round(sum(scores) / n, 1) if n else 0
        return {
            "exam_id": str(exam_id),
            "attempts": n,
            "mean_score_bp": mean,
            "pass_rate_bp": (
                int(round(10000 * sum(1 for a in attempts if a.passed) / n)) if n else 0
            ),
            "histogram": histogram,
            "questions": qstats,
        }

    async def analytics_csv(self, exam_id: uuid.UUID, user: User) -> str:
        """CSV export of the per-question analytics."""
        report = await self.analytics_report(exam_id, user)
        import csv
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            ["question_id", "qtype", "answered", "difficulty_bp", "discrimination", "prompt"]
        )
        for row in report["questions"]:
            w.writerow(
                [
                    row["question_id"],
                    row["qtype"],
                    row["answered"],
                    row["difficulty_bp"] if row["difficulty_bp"] is not None else "",
                    row["discrimination"] if row["discrimination"] is not None else "",
                    (row["prompt"] or "").replace("\n", " "),
                ]
            )
        return buf.getvalue()

    async def plagiarism_report(
        self, exam_id: uuid.UUID, user: User, *, threshold_bp: int = 7000
    ) -> list[dict]:
        """Cross-student plagiarism pass over the exam's essay answers.

        Pure Jaccard over ``_content_tokens`` (no AI calls, offline-safe): for
        each essay question, compares every pair of graded answers and reports
        pairs whose similarity is at or above ``threshold_bp``. Deterministic.
        """
        from app.ai.provider import _content_tokens
        from app.models.identity import User as _User

        await self._get_owned_exam(exam_id, user)
        questions = await self.list_questions(exam_id)
        essay_qids = {q.id for q in questions if q.qtype != "multiple_choice"}
        if not essay_qids:
            return []
        rows = (
            await self.session.execute(
                select(StudentAnswer, ExamAttempt, _User)
                .join(ExamAttempt, ExamAttempt.id == StudentAnswer.attempt_id)
                .join(_User, _User.id == ExamAttempt.user_id)
                .where(
                    StudentAnswer.question_id.in_(essay_qids),
                    StudentAnswer.graded_at.is_not(None),
                )
            )
        ).all()
        # Group answers by question.
        by_q: dict[uuid.UUID, list[tuple]] = {}
        for sa, attempt, owner in rows:
            if not (sa.answer_text or "").strip():
                continue
            by_q.setdefault(sa.question_id, []).append((sa, attempt, owner))

        query_by_q = {q.id: q for q in questions}
        findings: list[dict] = []
        for qid, entries in by_q.items():
            tokens = [
                set(_content_tokens(sa.answer_text or "")) for sa, _a, _o in entries
            ]
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    a_set, b_set = tokens[i], tokens[j]
                    if not a_set or not b_set:
                        continue
                    inter = len(a_set & b_set)
                    union = len(a_set | b_set)
                    sim_bp = int(round(inter / union * 10_000)) if union else 0
                    if sim_bp >= threshold_bp:
                        findings.append(
                            {
                                "question_id": str(qid),
                                "prompt": query_by_q[qid].prompt,
                                "a_attempt_id": str(entries[i][1].id),
                                "a_user_id": str(entries[i][1].user_id),
                                "a_name": entries[i][2].full_name,
                                "b_attempt_id": str(entries[j][1].id),
                                "b_user_id": str(entries[j][1].user_id),
                                "b_name": entries[j][2].full_name,
                                "similarity_bp": sim_bp,
                            }
                        )
        findings.sort(key=lambda f: f["similarity_bp"], reverse=True)
        return findings

    async def attempt_flag(self, attempt_id: uuid.UUID) -> tuple[bool, str | None, int]:
        """(is_flagged, reason, violation_count) for the results view."""
        attempt = await self.session.get(ExamAttempt, attempt_id)
        if attempt is None:
            return False, None, 0
        from app.models.exam import AttemptEvent

        count = (
            await self.session.execute(
                select(func.count())
                .select_from(AttemptEvent)
                .where(
                    AttemptEvent.attempt_id == attempt_id,
                    AttemptEvent.kind.in_(self._VIOLATION_KINDS),
                )
            )
        ).scalar_one()
        return bool(attempt.is_flagged), attempt.flag_reason, int(count)

    async def sweep_expired_attempts(self, *, limit: int = 50) -> int:
        """Auto-submit in-progress attempts whose server deadline has passed.

        Idempotent and safe under concurrency: rows are locked with SKIP LOCKED
        and only an attempt still ``in_progress`` is transitioned, so a second
        sweep (or a second worker) is a no-op. Expired attempts are submitted
        and queued for grading; the submitted_at is set to the deadline, not
        "now", so ranking reflects when the time actually ran out.
        """
        now = datetime.now(UTC)
        stmt = (
            select(ExamAttempt)
            .where(
                ExamAttempt.status == "in_progress",
                ExamAttempt.expires_at.is_not(None),
                ExamAttempt.expires_at < now,
            )
            .order_by(ExamAttempt.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        attempts = (await self.session.execute(stmt)).scalars().all()
        for attempt in attempts:
            attempt.submitted_at = attempt.expires_at or now
            attempt.status = "submitted"
            if attempt.started_at and attempt.submitted_at:
                attempt.duration_seconds = int(
                    (attempt.submitted_at - attempt.started_at).total_seconds()
                )
            # Queue grading for the auto-submitted attempt (idempotent).
            from app.services.grading_service import GradingService

            await GradingService(self.session).enqueue_if_absent(attempt)
        if attempts:
            await self.session.flush()
            log.info("expired_attempts_submitted", count=len(attempts))
        return len(attempts)

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
                "similarity_bp": sa.similarity_bp,
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
