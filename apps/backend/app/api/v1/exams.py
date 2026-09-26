"""Exam endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam, TeacherUser
from app.core.errors import ConflictError, ForbiddenError
from app.db.session import transaction
from app.middleware.rate_limit import rate_limit
from app.schemas.exam import (
    AnswerOut,
    AnswerUpsert,
    AttachQuestionIn,
    AttemptEventsIn,
    AttemptOut,
    AttemptResultOut,
    ExamCreate,
    ExamDetailOut,
    ExamOut,
    ExamResultReviewRow,
    ExamResultRow,
    ExamResultsReviewOut,
    ExamUpdate,
    OptionOut,
    OverrideAnswerIn,
    QuestionCreate,
    QuestionOut,
    QuestionReorder,
    QuestionUpdate,
    ReviewAnswerOut,
)
from app.services.audit import record as audit_record
from app.services.exam_service import ExamService
from app.services.grading_service import GradingService

router = APIRouter()


async def _question_out(service: ExamService, q, *, reveal_answers: bool) -> QuestionOut:
    """Serialise a question, including options. The correct option is only
    revealed to the exam owner/admin (never to students taking the exam)."""
    base = QuestionOut.model_validate(q)
    options = await service.options_for(q.id)
    base.options = [
        OptionOut(
            id=o.id,
            label=o.label,
            text=o.text,
            position=o.position,
            is_correct=(o.is_correct if reveal_answers else None),
        )
        for o in options
    ]
    if not reveal_answers:
        base = base.model_copy(update={"correct_answer": None})
    return base


async def _exam_out(service: ExamService, exam) -> ExamOut:
    """Serialise an exam with its (total, mc, essay) question counts."""
    counts = await service.question_counts([exam.id])
    total, mc, essay = counts.get(exam.id, (0, 0, 0))
    return ExamOut.model_validate(exam).model_copy(
        update={"question_count": total, "mc_count": mc, "essay_count": essay}
    )


@router.get("/exams", response_model=list[ExamOut])
async def list_exams(
    user: CurrentUser, db: DbSession, limit: LimitParam = 50, offset: OffsetParam = 0
):
    rows = await ExamService(db).list_all_with_counts(user, limit=limit, offset=offset)
    out: list[ExamOut] = []
    for exam, total, mc, essay in rows:
        base = ExamOut.model_validate(exam)
        out.append(
            base.model_copy(update={"question_count": total, "mc_count": mc, "essay_count": essay})
        )
    return out


@router.post("/exams", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
async def create_exam(payload: ExamCreate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await ExamService(db).create(user, **payload.model_dump())


@router.get("/exams/{exam_id}", response_model=ExamDetailOut)
async def get_exam(exam_id: uuid.UUID, user: CurrentUser, db: DbSession):
    service = ExamService(db)
    exam = await service.get(exam_id)
    # Students may only see published/active exams; teachers may preview any
    # active exam plus their own drafts.
    service.ensure_visible(exam, user)
    questions = await service.list_questions(exam_id)
    # Answer keys are only for the owner (or admins) — never leak them to the
    # students taking the exam.
    reveal_answers = user.has_role("admin") or exam.owner_id == user.id
    # Validate the base fields first: validating ExamDetailOut directly would
    # read the lazy ``questions`` relationship and raise MissingGreenlet.
    base = await _exam_out(service, exam)
    return ExamDetailOut(
        **base.model_dump(),
        questions=[
            await _question_out(service, q, reveal_answers=reveal_answers) for q in questions
        ],
    )


@router.patch("/exams/{exam_id}", response_model=ExamOut)
async def update_exam(exam_id: uuid.UUID, payload: ExamUpdate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await ExamService(db).update(exam_id, user, **payload.model_dump(exclude_unset=True))


@router.post("/exams/{exam_id}/publish", response_model=ExamOut)
async def publish_exam(exam_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await ExamService(db).publish(exam_id, user)


@router.post("/exams/{exam_id}/close", response_model=ExamOut)
async def close_exam(exam_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await ExamService(db).unpublish(exam_id, user)


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(exam_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        await ExamService(db).delete(exam_id, user)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(question_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        await ExamService(db).delete_question(question_id, user)


@router.get("/questions/bank", response_model=list[QuestionOut])
async def question_bank(
    user: TeacherUser, db: DbSession, limit: LimitParam = 50, offset: OffsetParam = 0
):
    """List the caller's questions across all exams (the question bank)."""
    service = ExamService(db)
    rows = await service.list_question_bank(user, limit=limit, offset=offset)
    out: list[QuestionOut] = []
    for q in rows:
        out.append(await _question_out(service, q, reveal_answers=True))
    return out


@router.post(
    "/exams/{exam_id}/questions/attach",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
)
async def attach_question(
    exam_id: uuid.UUID, payload: AttachQuestionIn, user: TeacherUser, db: DbSession
):
    """Copy an existing bank question into this exam (object-level owned)."""
    async with transaction(db):
        service = ExamService(db)
        clone = await service.attach_question(exam_id, payload.question_id, user)
        out = await _question_out(service, clone, reveal_answers=True)
    return out


@router.post("/exams/{exam_id}/questions/reorder", response_model=list[QuestionOut])
async def reorder_questions(
    exam_id: uuid.UUID, payload: QuestionReorder, user: TeacherUser, db: DbSession
):
    """Rewrite question positions from an explicit order (atomic)."""
    async with transaction(db):
        service = ExamService(db)
        questions = await service.reorder_questions(
            exam_id, user, payload.question_ids
        )
        out: list[QuestionOut] = []
        for q in questions:
            out.append(await _question_out(service, q, reveal_answers=True))
    return out


@router.post(
    "/exams/{exam_id}/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED
)
async def add_question(
    exam_id: uuid.UUID, payload: QuestionCreate, user: TeacherUser, db: DbSession
):
    data = payload.model_dump()
    options = data.pop("options", [])
    async with transaction(db):
        service = ExamService(db)
        question = await service.add_question(exam_id, user, options=options, **data)
        out = await _question_out(service, question, reveal_answers=True)
    return out


@router.patch("/questions/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: uuid.UUID, payload: QuestionUpdate, user: TeacherUser, db: DbSession
):
    data = payload.model_dump(exclude_unset=True)
    options = data.pop("options", None)
    async with transaction(db):
        service = ExamService(db)
        question = await service.update_question(question_id, user, options=options, **data)
        out = await _question_out(service, question, reveal_answers=True)
    return out


@router.post(
    "/exams/{exam_id}/attempts", response_model=AttemptOut, status_code=status.HTTP_201_CREATED
)
async def start_attempt(exam_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await ExamService(db).start_attempt(exam_id, user)


@router.get("/attempts", response_model=list[AttemptOut])
async def my_attempts(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    return await ExamService(db).my_attempts(user, limit=limit, offset=offset)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
async def get_attempt(attempt_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await ExamService(db).get_attempt(attempt_id, user)


@router.get("/attempts/{attempt_id}/questions", response_model=list[QuestionOut])
async def attempt_questions(attempt_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Questions + options for this attempt (deterministically shuffled).

    Answer keys are never revealed here; the shuffle is per-attempt and stable.
    """
    service = ExamService(db)
    rows = await service.attempt_questions(attempt_id, user)
    out: list[QuestionOut] = []
    for q, opts in rows:
        base = QuestionOut.model_validate(q)
        base.options = [
            OptionOut(id=o.id, label=o.label, text=o.text, position=o.position, is_correct=None)
            for o in opts
        ]
        out.append(base.model_copy(update={"correct_answer": None}))
    return out


@router.put("/attempts/{attempt_id}/answers/{question_id}", response_model=AnswerOut)
async def save_answer(
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: AnswerUpsert,
    user: CurrentUser,
    db: DbSession,
):
    async with transaction(db):
        return await ExamService(db).save_answer(attempt_id, question_id, user, payload.answer_text)


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptOut)
async def submit_attempt(attempt_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        service = ExamService(db)
        attempt = await service.submit_attempt(attempt_id, user)
        if attempt.status == "submitted":
            grading = GradingService(db)
            # Multiple-choice questions are graded deterministically; essay
            # questions need the AI provider. If the exam has any essay question
            # we enqueue a grading job (the worker scores MC instantly and then
            # the essays with AI). An MC-only exam is fully graded right here for
            # instant, gamified feedback.
            has_essay = await service.exam_has_essay(attempt.exam_id)
            if has_essay:
                await grading.enqueue_if_absent(attempt)
            else:
                attempt = await grading.grade_attempt(attempt)
            # If the exam belongs to an open quest, record the quest attempt so
            # winner finalization can consider it (server-authoritative time).
            await _record_quest_attempt_if_any(db, attempt, user)
    return attempt


async def _record_quest_attempt_if_any(db, attempt, user) -> None:
    from sqlalchemy import select

    from app.models.quest import Quest
    from app.services.quest_service import QuestService

    quest = (
        (
            await db.execute(
                select(Quest).where(Quest.exam_id == attempt.exam_id, Quest.status == "open")
            )
        )
        .scalars()
        .first()
    )
    if quest is not None:
        await QuestService(db).record_attempt(quest.id, user, exam_attempt_id=attempt.id)


@router.post("/attempts/{attempt_id}/regrade", response_model=AttemptOut)
async def regrade_attempt(attempt_id: uuid.UUID, user: TeacherUser, db: DbSession):
    """Re-enqueue grading for a failed attempt (teacher/admin retry).

    A permanently ``grading_failed`` attempt otherwise has no path back to a
    graded state. Only an attempt whose exam the caller owns (or an admin) may
    be re-graded.
    """
    async with transaction(db):
        service = ExamService(db)
        attempt = await service.get_attempt(attempt_id, user)
        exam = await service.get(attempt.exam_id)
        if not user.has_role("admin") and exam.owner_id != user.id:
            raise ForbiddenError("You do not own this exam")
        if attempt.status not in ("submitted", "grading_failed"):
            raise ConflictError("Only a submitted or failed attempt can be re-graded")
        grading = GradingService(db)
        await grading.reopen_for_regrade(attempt)
        # An MC-only exam is cheap to grade inline; otherwise the worker picks
        # up the re-queued job.
        if not await service.exam_has_essay(attempt.exam_id):
            attempt = await grading.grade_attempt(attempt)
    return attempt


@router.post("/attempts/{attempt_id}/answers/{question_id}/override", response_model=AnswerOut)
async def override_answer(
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: OverrideAnswerIn,
    user: TeacherUser,
    db: DbSession,
):
    """Manually override one answer's score (teacher/admin of the exam).

    Recomputes the attempt total and status, reverses the perfect-exam reward if
    the override makes the attempt non-flawless, and writes an AuditLog row.
    """
    async with transaction(db):
        service = ExamService(db)
        attempt = await service.get_attempt(attempt_id, user)
        exam = await service.get(attempt.exam_id)
        if not user.has_role("admin") and exam.owner_id != user.id:
            raise ForbiddenError("You do not own this exam")
        answer = await GradingService(db).override_answer(
            attempt=attempt,
            question_id=question_id,
            score_bp=payload.score_bp,
            feedback=payload.feedback,
        )
        audit_record(
            db,
            actor_id=user.id,
            action="exam.answer_override",
            entity_type="exam_attempt",
            entity_id=str(attempt.id),
            data={"question_id": str(question_id), "score_bp": answer.score_bp},
        )
    return answer


@router.post(
    "/attempts/{attempt_id}/events",
    dependencies=[Depends(rate_limit("ai", limit=120, window=60))],
)
async def record_attempt_events(
    attempt_id: uuid.UUID,
    payload: AttemptEventsIn,
    user: CurrentUser,
    db: DbSession,
):
    """Record proctoring telemetry (best-effort, rate-limited, never blocks).

    The client fires tab-blur/focus-loss/dwell events here; enough violations
    flag the attempt for the teacher. Errors are swallowed so telemetry can
    never break the exam flow.
    """
    async with transaction(db):
        try:
            n = await ExamService(db).record_events(
                attempt_id, user, [e.model_dump() for e in payload.events]
            )
        except Exception:  # noqa: BLE001 - telemetry must never break the flow
            n = 0
    return {"recorded": n}


@router.get("/attempts/{attempt_id}/result", response_model=AttemptResultOut)
async def attempt_result(attempt_id: uuid.UUID, user: CurrentUser, db: DbSession):
    service = ExamService(db)
    attempt = await service.get_attempt(attempt_id, user)
    answers = await service.list_answers(attempt_id)
    # Exam context is always returned so the result page renders even before the
    # worker finishes grading (and even if the exam was since closed).
    exam = await service.get(attempt.exam_id)
    # Review is only meaningful once the attempt is graded; before that we do
    # not reveal answer keys (that would let a retaker look up the answers).
    graded = attempt.status == "graded"
    questions = await service.list_questions(attempt.exam_id)
    return AttemptResultOut(
        attempt=AttemptOut.model_validate(attempt),
        exam=await _exam_out(service, exam),
        answers=[AnswerOut.model_validate(a) for a in answers],
        questions=(
            [await _question_out(service, q, reveal_answers=True) for q in questions]
            if graded
            else []
        ),
    )


@router.get("/exams/{exam_id}/results", response_model=list[ExamResultRow])
async def exam_results(
    exam_id: uuid.UUID,
    user: TeacherUser,
    db: DbSession,
    limit: LimitParam = 200,
    offset: OffsetParam = 0,
):
    rows = await ExamService(db).exam_results(exam_id, user, limit=limit, offset=offset)
    out: list[ExamResultRow] = []
    for attempt, name in rows:
        base = AttemptOut.model_validate(attempt)
        out.append(ExamResultRow(**base.model_dump(), display_name=name))
    return out


@router.get("/exams/{exam_id}/analytics")
async def exam_analytics(exam_id: uuid.UUID, user: TeacherUser, db: DbSession):
    """Score distribution, per-question difficulty and discrimination (owner)."""
    async with transaction(db):
        report = await ExamService(db).analytics_report(exam_id, user)
    return report


@router.get("/exams/{exam_id}/analytics.csv")
async def exam_analytics_csv(exam_id: uuid.UUID, user: TeacherUser, db: DbSession):
    """CSV export of the per-question analytics (owner only)."""
    from fastapi.responses import PlainTextResponse

    async with transaction(db):
        csv_text = await ExamService(db).analytics_csv(exam_id, user)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="exam-{exam_id}-analytics.csv"'},
    )


@router.get("/exams/{exam_id}/plagiarism")
async def plagiarism_report(
    exam_id: uuid.UUID, user: TeacherUser, db: DbSession, threshold_bp: int = 7000
):
    """Cross-student plagiarism report for the exam's essay answers (owner only).

    Deterministic (Jaccard over content tokens), no AI calls, offline-safe.
    """
    if threshold_bp < 0 or threshold_bp > 10_000:
        raise ConflictError("threshold_bp must be between 0 and 10000")
    async with transaction(db):
        findings = await ExamService(db).plagiarism_report(
            exam_id, user, threshold_bp=threshold_bp
        )
    return {"threshold_bp": threshold_bp, "findings": findings}


@router.get("/exams/{exam_id}/results/review", response_model=ExamResultsReviewOut)
async def exam_results_review(
    exam_id: uuid.UUID,
    user: TeacherUser,
    db: DbSession,
    limit: LimitParam = 200,
    offset: OffsetParam = 0,
):
    """Per-student answer review for an exam (owner/admin only).

    For each student who attempted the exam: their name, score/pass, and their
    answers to every question with the question text, the resolved answer
    (option text for multiple-choice), whether it was correct, and the score.
    """
    service = ExamService(db)
    exam, rows = await service.exam_review(exam_id, user, limit=limit, offset=offset)
    results: list[ExamResultReviewRow] = []
    for attempt, name, review in rows:
        base = AttemptOut.model_validate(attempt)
        flagged, reason, violations = await service.attempt_flag(attempt.id)
        results.append(
            ExamResultReviewRow(
                **base.model_dump(),
                display_name=name,
                answers=[ReviewAnswerOut(**payload) for payload in review.values()],
                is_flagged=flagged,
                flag_reason=reason,
                violation_count=violations,
            )
        )
    return ExamResultsReviewOut(exam=ExamOut.model_validate(exam), results=results)
