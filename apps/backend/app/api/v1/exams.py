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
    ExamUpdate,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
)
from app.services.exam_service import ExamService
from app.services.grading_service import GradingService

router = APIRouter()


@router.get("/exams", response_model=list[ExamOut])
async def list_exams(
    user: CurrentUser, db: DbSession, limit: LimitParam = 50, offset: OffsetParam = 0
):
    return await ExamService(db).list_all(user, limit=limit, offset=offset)


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
    base = ExamOut.model_validate(exam)
    return ExamDetailOut(
        **base.model_dump(),
        questions=[
            QuestionOut.model_validate(q).model_copy(
                update={} if reveal_answers else {"correct_answer": None}
            )
            for q in questions
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


@router.post(
    "/exams/{exam_id}/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED
)
async def add_question(
    exam_id: uuid.UUID, payload: QuestionCreate, user: TeacherUser, db: DbSession
):
    async with transaction(db):
        return await ExamService(db).add_question(exam_id, user, **payload.model_dump())


@router.patch("/questions/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: uuid.UUID, payload: QuestionUpdate, user: TeacherUser, db: DbSession
):
    async with transaction(db):
        return await ExamService(db).update_question(
            question_id, user, **payload.model_dump(exclude_unset=True)
        )


@router.post(
    "/exams/{exam_id}/attempts", response_model=AttemptOut, status_code=status.HTTP_201_CREATED
)
async def start_attempt(exam_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await ExamService(db).start_attempt(exam_id, user)


@router.get("/attempts", response_model=list[AttemptOut])
async def my_attempts(user: CurrentUser, db: DbSession):
    return await ExamService(db).my_attempts(user)


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
        # Enqueue grading (worker picks it up). Idempotent per attempt.
        if attempt.status == "submitted":
            await GradingService(db).enqueue_if_absent(attempt)
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
    return AttemptResultOut(
        attempt=AttemptOut.model_validate(attempt),
        answers=[AnswerOut.model_validate(a) for a in answers],
    )


@router.get("/exams/{exam_id}/results", response_model=list[AttemptOut])
async def exam_results(exam_id: uuid.UUID, user: TeacherUser, db: DbSession):
    return await ExamService(db).exam_results(exam_id, user)
