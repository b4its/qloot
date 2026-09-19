"""Exam endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, TeacherUser
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
async def list_exams(user: CurrentUser, db: DbSession, limit: int = 50, offset: int = 0):
    return await ExamService(db).list(user, limit=limit, offset=offset)


@router.post("/exams", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
async def create_exam(payload: ExamCreate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await ExamService(db).create(user, **payload.model_dump())


@router.get("/exams/{exam_id}", response_model=ExamDetailOut)
async def get_exam(exam_id: uuid.UUID, user: CurrentUser, db: DbSession):
    service = ExamService(db)
    exam = await service.get(exam_id)
    questions = await service.list_questions(exam_id)
    detail = ExamDetailOut.model_validate(exam)
    detail.questions = [QuestionOut.model_validate(q) for q in questions]
    return detail


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
    return attempt


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
