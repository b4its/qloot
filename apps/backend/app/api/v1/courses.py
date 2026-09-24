"""Pelajaran (subject) endpoints.

Class-based e-learning: teachers create subjects targeted at a class, students
see only the subjects matching their own class. No purchasing or enrolment.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam, TeacherUser
from app.db.session import transaction
from app.schemas.common import Message
from app.schemas.learning import (
    CourseCreate,
    CourseOut,
    CourseUpdate,
    LessonCreate,
    LessonOut,
    LessonReorder,
    LessonUpdate,
    ProgressOut,
    ProgressUpdate,
)
from app.services.course_service import CourseService

router = APIRouter()


@router.get("/courses", response_model=list[CourseOut])
async def list_courses(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    """Subjects visible to the caller (students: their class only)."""
    service = CourseService(db)
    courses = await service.list_for_user(user, limit=limit, offset=offset)
    return await service.out_payload(courses)


@router.get("/me/subjects", response_model=list[CourseOut])
async def my_subjects(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    """Convenience alias: the subjects the current user can access."""
    service = CourseService(db)
    courses = await service.list_for_user(user, limit=limit, offset=offset)
    return await service.out_payload(courses)


@router.post("/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(payload: CourseCreate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        service = CourseService(db)
        course = await service.create(user, **payload.model_dump())
        return (await service.out_payload([course]))[0]


@router.get("/courses/{course_id}", response_model=CourseOut)
async def get_course(course_id: uuid.UUID, user: CurrentUser, db: DbSession):
    service = CourseService(db)
    course = await service.get_accessible(course_id, user)
    return (await service.out_payload([course]))[0]


@router.patch("/courses/{course_id}", response_model=CourseOut)
async def update_course(
    course_id: uuid.UUID, payload: CourseUpdate, user: TeacherUser, db: DbSession
):
    async with transaction(db):
        service = CourseService(db)
        course = await service.update(course_id, user, **payload.model_dump(exclude_unset=True))
        return (await service.out_payload([course]))[0]


@router.delete("/courses/{course_id}", response_model=Message)
async def delete_course(course_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        await CourseService(db).delete(course_id, user)
    return Message(message="Pelajaran dihapus")


@router.get("/courses/{course_id}/lessons", response_model=list[LessonOut])
async def list_lessons(
    course_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    service = CourseService(db)
    course = await service.get_accessible(course_id, user)
    # Draft lessons are only visible to the owner/admin; students see published
    # lessons only (a staged lesson must not leak).
    owner = user.has_role("admin") or course.owner_id == user.id
    return await service.list_lessons(
        course_id, limit=limit, offset=offset, published_only=not owner
    )


@router.post(
    "/courses/{course_id}/lessons", response_model=LessonOut, status_code=status.HTTP_201_CREATED
)
async def create_lesson(
    course_id: uuid.UUID, payload: LessonCreate, user: TeacherUser, db: DbSession
):
    async with transaction(db):
        return await CourseService(db).add_lesson(course_id, user, **payload.model_dump())


@router.get("/lessons/{lesson_id}", response_model=LessonOut)
async def get_lesson(lesson_id: uuid.UUID, user: CurrentUser, db: DbSession):
    service = CourseService(db)
    lesson = await service.get_lesson(lesson_id)
    course = await service.get_accessible(lesson.course_id, user)
    owner = user.has_role("admin") or course.owner_id == user.id
    if not lesson.is_published and not owner:
        from app.core.errors import NotFoundError

        raise NotFoundError("Materi pelajaran tidak ditemukan")
    return lesson


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
async def update_lesson(
    lesson_id: uuid.UUID, payload: LessonUpdate, user: TeacherUser, db: DbSession
):
    async with transaction(db):
        return await CourseService(db).update_lesson(
            lesson_id, user, **payload.model_dump(exclude_unset=True)
        )


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(lesson_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        await CourseService(db).delete_lesson(lesson_id, user)


@router.post("/courses/{course_id}/lessons/reorder", response_model=list[LessonOut])
async def reorder_lessons(
    course_id: uuid.UUID, payload: LessonReorder, user: TeacherUser, db: DbSession
):
    """Rewrite lesson positions from an explicit order (atomic)."""
    async with transaction(db):
        lessons = await CourseService(db).reorder_lessons(
            course_id, user, payload.lesson_ids
        )
    return lessons


@router.post("/lessons/{lesson_id}/progress", response_model=ProgressOut)
async def set_progress(
    lesson_id: uuid.UUID, payload: ProgressUpdate, user: CurrentUser, db: DbSession
):
    async with transaction(db):
        progress = await CourseService(db).set_progress(
            lesson_id, user, progress_percent=payload.progress_percent, completed=payload.completed
        )
        # Completing the final lesson of a course issues a (simulated) certificate.
        if payload.completed:
            from app.services.certificate_service import CertificateService

            await CertificateService(db).issue_for_course(user, progress.course_id)
        return progress


@router.get("/me/learning-progress", response_model=list[ProgressOut])
async def my_progress(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    return await CourseService(db).my_progress(user, limit=limit, offset=offset)


@router.get("/lessons/{lesson_id}/materials")
async def lesson_materials(
    lesson_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    """Materials attached to a lesson (visible to the lesson's course members).

    Students see the PDFs/notes for their own class; teachers and admins see
    everything. A lesson outside the caller's class returns 403.
    """
    from app.schemas.material import MaterialOut
    from app.services.material_service import MaterialService

    rows = await MaterialService(db).list_for_lesson(lesson_id, user, limit=limit, offset=offset)
    return [MaterialOut.model_validate(m) for m in rows]
