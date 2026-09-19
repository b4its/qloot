"""Learning endpoints: courses, lessons, progress."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, TeacherUser
from app.db.session import transaction
from app.schemas.common import Message
from app.schemas.learning import (
    CourseCreate,
    CourseOut,
    CourseUpdate,
    LessonCreate,
    LessonOut,
    LessonUpdate,
    ProgressOut,
    ProgressUpdate,
)
from app.services.course_service import CourseService

router = APIRouter()


@router.get("/courses", response_model=list[CourseOut])
async def list_courses(user: CurrentUser, db: DbSession, limit: int = 50, offset: int = 0):
    # Students only see published courses; teachers/admins see all.
    published_only = not user.has_role("teacher", "admin")
    service = CourseService(db)
    return await service.list_all(published_only=published_only, limit=limit, offset=offset)


@router.post("/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(payload: CourseCreate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await CourseService(db).create(user, **payload.model_dump())


@router.get("/courses/{course_id}", response_model=CourseOut)
async def get_course(course_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await CourseService(db).get(course_id)


@router.patch("/courses/{course_id}", response_model=CourseOut)
async def update_course(
    course_id: uuid.UUID, payload: CourseUpdate, user: TeacherUser, db: DbSession
):
    async with transaction(db):
        return await CourseService(db).update(
            course_id, user, **payload.model_dump(exclude_unset=True)
        )


@router.delete("/courses/{course_id}", response_model=Message)
async def delete_course(course_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        await CourseService(db).delete(course_id, user)
    return Message(message="Course deleted")


@router.get("/courses/{course_id}/lessons", response_model=list[LessonOut])
async def list_lessons(course_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await CourseService(db).list_lessons(course_id)


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
    return await CourseService(db).get_lesson(lesson_id)


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
async def update_lesson(
    lesson_id: uuid.UUID, payload: LessonUpdate, user: TeacherUser, db: DbSession
):
    async with transaction(db):
        return await CourseService(db).update_lesson(
            lesson_id, user, **payload.model_dump(exclude_unset=True)
        )


@router.post("/lessons/{lesson_id}/progress", response_model=ProgressOut)
async def set_progress(
    lesson_id: uuid.UUID, payload: ProgressUpdate, user: CurrentUser, db: DbSession
):
    async with transaction(db):
        return await CourseService(db).set_progress(
            lesson_id, user, progress_percent=payload.progress_percent, completed=payload.completed
        )


@router.get("/me/learning-progress", response_model=list[ProgressOut])
async def my_progress(user: CurrentUser, db: DbSession):
    return await CourseService(db).my_progress(user)
