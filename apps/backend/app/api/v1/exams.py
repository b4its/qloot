"""Exam endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam, TeacherUser
from app.db.session import transaction
from app.schemas.exam import (
    AnswerOut,
    AnswerUpsert,
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
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
    ReviewAnswerOut,
)
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
        results.append(
            ExamResultReviewRow(
                **base.model_dump(),
                display_name=name,
                answers=[ReviewAnswerOut(**payload) for payload in review.values()],
            )
        )
    return ExamResultsReviewOut(exam=ExamOut.model_validate(exam), results=results)
