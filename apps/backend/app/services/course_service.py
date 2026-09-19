"""Course service: CRUD with ownership enforcement."""

from __future__ import annotations

import re
import uuid
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.identity import User
from app.models.learning import Course, CourseMember, Lesson, LessonProgress


def slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return s or uuid.uuid4().hex[:8]


class CourseService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, owner: User, **data) -> Course:
        slug = data.pop("slug", None) or slugify(data["title"])
        existing = (
            await self.session.execute(select(Course).where(Course.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("A course with this slug already exists")
        course = Course(owner_id=owner.id, slug=slug, **data)
        self.session.add(course)
        await self.session.flush()
        # Owner is also a member (teacher role in the course).
        self.session.add(CourseMember(course_id=course.id, user_id=owner.id, role="teacher"))
        await self.session.flush()
        return course

    async def get(self, course_id: uuid.UUID) -> Course:
        course = await self.session.get(Course, course_id)
        if course is None:
            raise NotFoundError("Course not found")
        return course

    async def list_all(
        self, *, published_only: bool = True, limit: int = 50, offset: int = 0
    ) -> list[Course]:
        stmt = select(Course).order_by(Course.created_at.desc()).limit(limit).offset(offset)
        if published_only:
            stmt = stmt.where(Course.is_published.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())

    async def update(self, course_id: uuid.UUID, user: User, **data) -> Course:
        course = await self.get(course_id)
        self._authorize(course, user)
        for k, v in data.items():
            if v is not None:
                setattr(course, k, v)
        await self.session.flush()
        return course

    async def delete(self, course_id: uuid.UUID, user: User) -> None:
        course = await self.get(course_id)
        self._authorize(course, user)
        await self.session.delete(course)

    # --- lessons -----------------------------------------------------------
    async def add_lesson(self, course_id: uuid.UUID, user: User, **data) -> Lesson:
        course = await self.get(course_id)
        self._authorize(course, user)
        lesson = Lesson(course_id=course.id, **data)
        self.session.add(lesson)
        await self.session.flush()
        return lesson

    async def get_lesson(self, lesson_id: uuid.UUID) -> Lesson:
        lesson = await self.session.get(Lesson, lesson_id)
        if lesson is None:
            raise NotFoundError("Lesson not found")
        return lesson

    async def list_lessons(self, course_id: uuid.UUID) -> list[Lesson]:
        stmt = select(Lesson).where(Lesson.course_id == course_id).order_by(Lesson.position)
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_lesson(self, lesson_id: uuid.UUID, user: User, **data) -> Lesson:
        lesson = await self.get_lesson(lesson_id)
        course = await self.get(lesson.course_id)
        self._authorize(course, user)
        for k, v in data.items():
            if v is not None:
                setattr(lesson, k, v)
        await self.session.flush()
        return lesson

    async def set_progress(
        self, lesson_id: uuid.UUID, user: User, *, progress_percent: int, completed: bool
    ) -> LessonProgress:
        from datetime import datetime

        lesson = await self.get_lesson(lesson_id)
        stmt = select(LessonProgress).where(
            LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id
        )
        progress = (await self.session.execute(stmt)).scalar_one_or_none()
        if progress is None:
            progress = LessonProgress(
                user_id=user.id,
                lesson_id=lesson_id,
                course_id=lesson.course_id,
                progress_percent=progress_percent,
                completed=completed,
            )
            self.session.add(progress)
        else:
            progress.progress_percent = max(progress.progress_percent, progress_percent)
            progress.completed = progress.completed or completed
        if completed and progress.completed_at is None:
            progress.completed_at = datetime.now(UTC)
        await self.session.flush()
        return progress

    async def my_progress(self, user: User) -> list[LessonProgress]:
        stmt = select(LessonProgress).where(LessonProgress.user_id == user.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def enroll(self, course_id: uuid.UUID, user: User) -> CourseMember:
        """Join a published course (idempotent)."""
        course = await self.get(course_id)
        if not course.is_published and not (user.has_role("admin") or course.owner_id == user.id):
            raise ForbiddenError("Course is not open for enrolment")
        stmt = select(CourseMember).where(
            CourseMember.course_id == course_id, CourseMember.user_id == user.id
        )
        member = (await self.session.execute(stmt)).scalar_one_or_none()
        if member is None:
            member = CourseMember(course_id=course_id, user_id=user.id, role="student")
            self.session.add(member)
            await self.session.flush()
        return member

    async def enrolled(self, user: User) -> list[CourseMember]:
        stmt = select(CourseMember).where(CourseMember.user_id == user.id)
        return list((await self.session.execute(stmt)).scalars().all())

    def _authorize(self, course: Course, user: User) -> None:
        if user.has_role("admin"):
            return
        if course.owner_id != user.id:
            raise ForbiddenError("You do not own this course")
