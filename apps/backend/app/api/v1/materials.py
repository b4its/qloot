"""Material upload + AI generation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam, TeacherUser
from app.core.config import settings
from app.core.errors import ValidationError
from app.db.session import transaction
from app.models.exam import Question, QuestionOption
from app.schemas.exam import OptionOut, QuestionOut
from app.schemas.material import (
    AnswerOut,
    AskRequest,
    GeneratedQuestionOut,
    GenerateQuestionsRequest,
    GenerationJobOut,
    MaterialOut,
    MaterialUpdate,
    SummaryOut,
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
    # Bound the read so an oversized upload is rejected *before* it is fully
    # buffered/parsed in memory (the size guard inside the service runs too late
    # for that). Read in chunks and abort as soon as the cap is exceeded.
    max_bytes = settings.ai_max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError(f"File exceeds the {max_bytes} byte limit")
        chunks.append(chunk)
    content = b"".join(chunks)
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


@router.get("", response_model=list[MaterialOut])
async def list_materials(
    user: TeacherUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    """List materials owned by the caller (most recent first)."""
    rows = await MaterialService(db).list_for_owner(user, limit=limit, offset=offset)
    return [MaterialOut.model_validate(m) for m in rows]


@router.get("/{material_id}", response_model=MaterialOut)
async def get_material(material_id: uuid.UUID, user: CurrentUser, db: DbSession):
    # Enforce the same visibility rule as summarize/ask (owner, admin, or an
    # enrolled student) — previously any authenticated user could read metadata.
    material = await MaterialService(db).get_viewable(material_id, user)
    return MaterialOut.model_validate(material)


@router.get("/{material_id}/download")
async def download_material(material_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Stream the stored material file back to an authorised viewer.

    Uploaded materials were previously write-only (no read path); this lets a
    teacher/student actually retrieve the PDF.
    """
    from urllib.parse import quote

    from fastapi import Response

    data, filename, content_type = await MaterialService(db).download(material_id, user)
    return Response(
        content=data,
        media_type=content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Content-Length": str(len(data)),
        },
    )


@router.patch("/{material_id}", response_model=MaterialOut)
async def update_material(
    material_id: uuid.UUID, payload: MaterialUpdate, user: TeacherUser, db: DbSession
):
    async with transaction(db):
        material = await MaterialService(db).update(material_id, user, filename=payload.filename)
    return MaterialOut.model_validate(material)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(material_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        await MaterialService(db).delete(material_id, user)


@router.post("/{material_id}/generate-questions", response_model=GenerationJobOut)
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
    return GenerationJobOut(job_id=job.id, status=job.status)


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


@router.get("/{material_id}/questions", response_model=list[QuestionOut])
async def material_questions(
    material_id: uuid.UUID,
    user: TeacherUser,
    db: DbSession,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    """Draft questions generated from a material (owner/admin only).

    Async generation creates questions detached from any exam; this surfaces the
    ones still awaiting review so a teacher can approve/reject them instead of
    them becoming orphaned. Approved/rejected questions are excluded (they are
    no longer drafts).
    """
    service = MaterialService(db)
    material = await service.get_viewable(material_id, user)
    stmt = (
        select(Question)
        .where(Question.material_id == material.id, Question.review_status == "pending")
        .order_by(Question.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return []
    # Batch-load every option in one query (never N+1).
    option_rows = (
        (
            await db.execute(
                select(QuestionOption).where(QuestionOption.question_id.in_([q.id for q in rows]))
            )
        )
        .scalars()
        .all()
    )
    by_question: dict[uuid.UUID, list[QuestionOption]] = {}
    for o in option_rows:
        by_question.setdefault(o.question_id, []).append(o)
    out: list[QuestionOut] = []
    for q in rows:
        item = QuestionOut.model_validate(q)
        item.options = [
            OptionOut(
                id=o.id, label=o.label, text=o.text, position=o.position, is_correct=o.is_correct
            )
            for o in sorted(by_question.get(q.id, []), key=lambda x: x.position)
        ]
        out.append(item)
    return out


@router.get("/{material_id}/summary", response_model=SummaryOut)
async def material_summary(
    material_id: uuid.UUID, user: CurrentUser, db: DbSession, language: str = "id"
):
    """AI summary of the material for learners."""
    result = await MaterialService(db).summarize(material_id, user, language=language)
    return SummaryOut(summary=result.summary, key_points=result.key_points)


@router.post("/{material_id}/ask", response_model=AnswerOut)
async def material_ask(
    material_id: uuid.UUID, payload: AskRequest, user: CurrentUser, db: DbSession
):
    """Ask the material a question (grounded AI Q&A)."""
    result = await MaterialService(db).ask(
        material_id, user, question=payload.question, language=payload.language
    )
    return AnswerOut(answer=result.answer, confidence_bp=result.confidence_bp)
