"""Course-scoped lesson progress (``GET /me/learning-progress?course_id=``).

A course detail page shows its own per-lesson completion; the endpoint supports
scoping to a single course so the client never over-fetches the whole history.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _mk_user(session):
    from tests.conftest import provision_user

    return await provision_user(session, email=f"prog_{uuid.uuid4().hex[:8]}@ex.com")


async def _mk_course(session, owner_id) -> uuid.UUID:
    from app.models.learning import Course

    course_id = uuid.uuid4()
    session.add(
        Course(
            id=course_id,
            title="C",
            slug=f"c-{uuid.uuid4().hex[:8]}",
            class_code="1A",
            class_type="IPA",
            owner_id=owner_id,
        )
    )
    await session.flush()
    return course_id


async def _mk_progress(session, user_id, course_id, completed: bool):
    from app.models.learning import Lesson, LessonProgress

    lesson = Lesson(
        id=uuid.uuid4(),
        course_id=course_id,
        title="L",
        position=0,
        is_published=True,
    )
    session.add(lesson)
    await session.flush()
    session.add(
        LessonProgress(
            id=uuid.uuid4(),
            user_id=user_id,
            lesson_id=lesson.id,
            course_id=course_id,
            completed=completed,
            progress_percent=100 if completed else 0,
        )
    )
    await session.flush()
    return lesson.id


async def test_progress_can_be_scoped_to_one_course(client, session):
    """Scoping returns only the requested course's progress rows."""
    user = await _mk_user(session)
    c1 = await _mk_course(session, user.id)
    c2 = await _mk_course(session, user.id)
    await _mk_progress(session, user.id, c1, completed=True)
    await _mk_progress(session, user.id, c2, completed=False)
    await session.commit()

    # Log the user in.
    login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "Password123!"}
    )
    assert login.status_code == 200, login.text

    r = await client.get(f"/api/v1/me/learning-progress?course_id={c1}")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["course_id"] == str(c1)
    assert rows[0]["completed"] is True

    # Without the filter, both courses' progress appears.
    allrows = (await client.get("/api/v1/me/learning-progress?limit=200")).json()
    course_ids = {row["course_id"] for row in allrows}
    assert {str(c1), str(c2)} <= course_ids
