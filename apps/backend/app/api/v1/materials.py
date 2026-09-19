"""Material upload + AI generation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import CurrentUser, DbSession, TeacherUser
from app.db.session import transaction
from app.models.exam import Question
from app.schemas.material import (
    GeneratedQuestionOut,
    GenerateQuestionsRequest,
    MaterialOut,
)
from app.services.material_service import MaterialService

router = APIRouter()


@router.post("/upload", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
async def upload_material(
    user: TeacherUser,
    db: DbSession,
    file: UploadFile = File(...),
    course_id: uuid.UUID | None = Form(default=None),
    lesson_id: uuid.UUID | None = Form(default=None),
):
    content = await file.read()
    async with transaction(db):
        material = await MaterialService(db).upload(
            user,
            filename=file.filename or "material.pdf",
            content=content,
            content_type=file.content_type or "application/pdf",
            course_id=course_id,
            lesson_id=lesson_id,
        )
    return MaterialOut.model_validate(material)


@router.get("/{material_id}", response_model=MaterialOut)
async def get_material(material_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return MaterialOut.model_validate(await MaterialService(db).get(material_id))


@router.post("/{material_id}/generate-questions", response_model=dict)
async def generate_questions(
    material_id: uuid.UUID,
    payload: GenerateQuestionsRequest,
    user: TeacherUser,
    db: DbSession,
):
    """Enqueue a generation job (processed by the worker) and return its id."""
    async with transaction(db):
        job = await MaterialService(db).enqueue_generation(
            material_id,
            user,
            count=payload.count,
            language=payload.language,
            exam_id=payload.exam_id,
        )
    return {"job_id": str(job.id), "status": job.status}


@router.post("/{material_id}/generate-questions-sync", response_model=list[GeneratedQuestionOut])
async def generate_questions_sync(
    material_id: uuid.UUID,
    payload: GenerateQuestionsRequest,
    user: TeacherUser,
    db: DbSession,
):
    """Synchronous generation for local/dev use (bypasses the queue)."""
    async with transaction(db):
        service = MaterialService(db)
        job = await service.enqueue_generation(
            material_id,
            user,
            count=payload.count,
            language=payload.language,
            exam_id=payload.exam_id,
        )
        questions: list[Question] = await service.run_generation(job)
        job.status = "done"
    return [
        GeneratedQuestionOut(
            id=q.id,
            prompt=q.prompt,
            correct_answer=q.correct_answer,
            max_score_bp=q.max_score_bp,
            review_status=q.review_status,
        )
        for q in questions
    ]
