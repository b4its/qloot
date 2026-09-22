"""Subject ("pelajaran") service.

QLoot is a class-based e-learning system: teachers create subjects targeted at
a class (e.g. "1A") and programme (e.g. "IPA"), and students automatically see
the subjects that match their own class. There is no purchasing or enrolment.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.identity import User
from app.models.learning import Course, CourseMember, Lesson, LessonProgress


def slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return s or uuid.uuid4().hex[:8]


def normalize_class_code(value: str) -> str:
    """Normalise a class code: trimmed, uppercase, no internal spaces ('1a'->'1A')."""
    return re.sub(r"\s+", "", value).upper()


def normalize_class_type(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", "", value).upper()


class CourseService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- create / read -----------------------------------------------------
    async def create(self, owner: User, **data) -> Course:
        title = data["title"]
        slug = data.pop("slug", None) or slugify(title)
        class_code = normalize_class_code(data.get("class_code") or "UMUM")
        class_type = normalize_class_type(data.get("class_type"))
        # A subject is unique per (class, class_type, title).
        dup = (
            await self.session.execute(
                select(Course).where(
                    Course.class_code == class_code,
                    func.coalesce(Course.class_type, "") == (class_type or ""),
                    func.lower(Course.title) == title.lower(),
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            raise ConflictError("Subjek dengan kelas dan nama yang sama sudah ada")

        base_slug = slug
        while (
            await self.session.execute(select(Course).where(Course.slug == slug))
        ).scalar_one_or_none() is not None:
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        course = Course(
            owner_id=owner.id,
            slug=slug,
            class_code=class_code,
            class_type=class_type,
            **{k: v for k, v in data.items() if k not in ("class_code", "class_type")},
        )
        self.session.add(course)
        await self.session.flush()
        self.session.add(CourseMember(course_id=course.id, user_id=owner.id, role="teacher"))
        await self.session.flush()
        return course

    async def get(self, course_id: uuid.UUID) -> Course:
        course = await self.session.get(Course, course_id)
        if course is None:
            raise NotFoundError("Pelajaran tidak ditemukan")
        return course

    async def get_accessible(self, course_id: uuid.UUID, user: User) -> Course:
        """Fetch a subject only if the user may view it (owner, admin or same class)."""
        course = await self.get(course_id)
        if not self.can_view(course, user):
            raise ForbiddenError("Anda tidak memiliki akses ke pelajaran ini")
        return course

    def can_view(self, course: Course, user: User) -> bool:
        if user.has_role("admin") or course.owner_id == user.id:
            return True
        # Students may view a published subject that targets their class, or a
        # subject explicitly broadcast to all classes ("UMUM"). A subject with
        # no class_code is NOT public (it must be targeted or broadcast).
        if not course.is_published:
            return False
        if course.class_code == "UMUM":
            return True
        if not user.class_code or not course.class_code:
            return False
        if normalize_class_code(user.class_code) != course.class_code:
            return False
        if course.class_type:
            return normalize_class_type(user.class_type) == course.class_type
        return True

    async def list_for_user(self, user: User, *, limit: int = 100, offset: int = 0) -> list[Course]:
        """Subjects visible to the user.

        - teacher/admin: subjects they own (admin: all)
        - student: published subjects matching their class (or broadcast "UMUM")
        """
        stmt = select(Course).order_by(Course.class_code, Course.title).limit(limit).offset(offset)
        if user.has_role("admin"):
            pass
        elif user.has_role("teacher"):
            stmt = stmt.where(Course.owner_id == user.id)
        else:
            if not user.class_code:
                return []
            cc = normalize_class_code(user.class_code)
            ct = normalize_class_type(user.class_type)
            stmt = stmt.where(Course.is_published.is_(True)).where(
                (Course.class_code.in_([cc, "UMUM"]))
                & ((Course.class_type.is_(None)) | (Course.class_type == ct))
            )
        return list((await self.session.execute(stmt)).scalars().all())

    async def out_payload(self, courses: list[Course]) -> list[dict]:
        """Serialize courses with owner name and lesson count (avoids N+1)."""
        if not courses:
            return []
        ids = [c.id for c in courses]
        owner_ids = {c.owner_id for c in courses}
        owners = {
            u.id: u.full_name
            for u in (await self.session.execute(select(User).where(User.id.in_(owner_ids))))
            .scalars()
            .all()
        }
        rows = (
            await self.session.execute(
                select(Lesson.course_id, func.count(Lesson.id))
                .where(Lesson.course_id.in_(ids))
                .group_by(Lesson.course_id)
            )
        ).all()
        counts: dict[uuid.UUID, int] = {row[0]: int(row[1]) for row in rows}
        out = []
        for c in courses:
            out.append(
                {
                    "id": c.id,
                    "title": c.title,
                    "slug": c.slug,
                    "description": c.description,
                    "owner_id": c.owner_id,
                    "owner_name": owners.get(c.owner_id),
                    "is_published": c.is_published,
                    "cover_url": c.cover_url,
                    "subject": c.subject,
                    "class_code": c.class_code,
                    "class_type": c.class_type,
                    "lesson_count": int(counts.get(c.id, 0)),
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                }
            )
        return out

    async def update(self, course_id: uuid.UUID, user: User, **data) -> Course:
        course = await self.get(course_id)
        self._authorize(course, user)
        if data.get("class_code"):
            data["class_code"] = normalize_class_code(data["class_code"])
        if "class_type" in data:
            data["class_type"] = normalize_class_type(data.get("class_type"))
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
            raise NotFoundError("Materi pelajaran tidak ditemukan")
        return lesson

    async def list_lessons(
        self, course_id: uuid.UUID, *, limit: int = 200, offset: int = 0
    ) -> list[Lesson]:
        stmt = (
            select(Lesson)
            .where(Lesson.course_id == course_id)
            .order_by(Lesson.position)
            .limit(limit)
            .offset(offset)
        )
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

    async def delete_lesson(self, lesson_id: uuid.UUID, user: User) -> None:
        lesson = await self.get_lesson(lesson_id)
        course = await self.get(lesson.course_id)
        self._authorize(course, user)
        await self.session.delete(lesson)
        await self.session.flush()

    async def set_progress(
        self, lesson_id: uuid.UUID, user: User, *, progress_percent: int, completed: bool
    ) -> LessonProgress:
        lesson = await self.get_lesson(lesson_id)
        course = await self.get(lesson.course_id)
        if not self.can_view(course, user):
            raise ForbiddenError("Anda tidak memiliki akses ke materi ini")
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

        # Badges for learning milestones (ids are deterministic by threshold).
        if completed:
            from sqlalchemy import func as _func

            from app.services.social_service import BadgeService

            done = (
                await self.session.execute(
                    select(_func.count(LessonProgress.id)).where(
                        LessonProgress.user_id == user.id,
                        LessonProgress.completed.is_(True),
                    )
                )
            ).scalar_one()
            badges = BadgeService(self.session)
            if done >= 5:
                # "Dedicated Learner": completed 5 lessons. (quiz_master is
                # reserved for acing a multiple-choice quiz.)
                await badges.award(user=user, code="learner")
        return progress

    async def my_progress(
        self, user: User, *, limit: int = 100, offset: int = 0
    ) -> list[LessonProgress]:
        stmt = (
            select(LessonProgress)
            .where(LessonProgress.user_id == user.id)
            .order_by(LessonProgress.id)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def my_subjects(self, user: User) -> list[Course]:
        """Alias with clearer semantics for students."""
        return await self.list_for_user(user)

    # --- authorization -----------------------------------------------------
    def _authorize(self, course: Course, user: User) -> None:
        if user.has_role("admin"):
            return
        if course.owner_id != user.id:
            raise ForbiddenError("Anda tidak memiliki pelajaran ini")
