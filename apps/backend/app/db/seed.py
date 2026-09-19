"""Seed demo data: roles, an admin, a teacher, students, a course, an exam.

Run with: `python -m app.db.seed` (idempotent).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope
from app.models.identity import Role, User
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService
from app.services.course_service import CourseService

log = get_logger("seed")

ROLES = [
    ("student", "Learner who takes quests and earns OPC"),
    ("teacher", "Creates materials, exams, rooms and quests"),
    ("admin", "Platform administrator"),
]


async def _ensure_roles() -> None:
    async with session_scope() as session:
        for name, desc in ROLES:
            existing = (
                await session.execute(select(Role).where(Role.name == name))
            ).scalar_one_or_none()
            if existing is None:
                session.add(Role(name=name, description=desc))


async def _ensure_user(email: str, full_name: str, password: str, role: str) -> User:
    async with session_scope() as session:
        users = UserRepository(session)
        existing = await users.get_by_email(email)
        if existing is not None:
            log.info("seed_user_exists", email=email)
            return existing
        auth = AuthService(session)
        user, _ = await auth.register(
            email=email, full_name=full_name, password=password, role=role
        )
        log.info("seed_user_created", email=email, role=role)
        return user


async def main() -> None:
    configure_logging()
    await _ensure_roles()
    admin = await _ensure_user("admin@qloot.example", "QLoot Admin", "AdminPass123!", "admin")
    teacher = await _ensure_user("teacher@qloot.example", "Budi Guru", "TeacherPass123!", "teacher")
    for i in range(1, 4):
        await _ensure_user(f"student{i}@qloot.example", f"Siswa {i}", "StudentPass123!", "student")

    # A sample course owned by the teacher.
    async with session_scope() as session:
        from app.models.learning import Course

        existing = (
            await session.execute(select(Course).where(Course.slug == "dasar-pemrograman"))
        ).scalar_one_or_none()
        if existing is None:
            course = await CourseService(session).create(
                teacher,
                title="Dasar Pemrograman",
                description="Pengantar konsep dasar pemrograman.",
                is_published=True,
            )
            await CourseService(session).add_lesson(
                course.id,
                teacher,
                title="Pengenalan Variabel",
                content_md="# Variabel\nVariabel adalah wadah nilai.",
                is_published=True,
            )
            log.info("seed_course_created")

    log.info("seed_done", admin=str(admin.id), teacher=str(teacher.id))


if __name__ == "__main__":
    asyncio.run(main())
