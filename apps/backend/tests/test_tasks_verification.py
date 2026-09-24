"""Task completion is verified against the underlying event (GAME-04).

A task bound to a course/quest must not be completable by self-report alone
— the student has to have actually completed a lesson in that course, or have
a valid quest attempt, before the reward is granted. Tasks with neither
binding remain honor-system (unchanged).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher", *, class_code=None):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Verify User", class_code=class_code)


async def test_course_bound_task_rejected_without_lesson_completion(client):
    await _register(client, "verify_teacher@ex.com", "teacher")
    course = await client.post(
        "/api/v1/courses",
        json={"title": "Biologi", "class_code": "1A", "is_published": True},
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]

    lesson = await client.post(
        f"/api/v1/courses/{course_id}/lessons",
        json={"title": "Fotosintesis", "content_md": "Isi", "is_published": True},
    )
    assert lesson.status_code == 201, lesson.text

    task = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Selesaikan Biologi",
            "kind": "learning",
            "reward_amount": 15,
            "course_id": course_id,
        },
    )
    assert task.status_code == 201, task.text
    assert task.json()["honor_system"] is False
    task_id = task.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "verify_student@ex.com", "student", class_code="1A")

    # No lesson progress yet -> the task cannot be completed.
    r = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert r.status_code == 409, r.text
    assert "pelajaran" in r.json()["error"]["message"].lower()


async def test_course_bound_task_accepted_after_lesson_completion(client):
    await _register(client, "verify_teacher2@ex.com", "teacher")
    course = await client.post(
        "/api/v1/courses",
        json={"title": "Kimia", "class_code": "1A", "is_published": True},
    )
    course_id = course.json()["id"]
    lesson = await client.post(
        f"/api/v1/courses/{course_id}/lessons",
        json={"title": "Reaksi kimia", "content_md": "Isi", "is_published": True},
    )
    lesson_id = lesson.json()["id"]

    task = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Selesaikan Kimia",
            "kind": "learning",
            "reward_amount": 15,
            "course_id": course_id,
        },
    )
    task_id = task.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "verify_student2@ex.com", "student", class_code="1A")

    # Complete the lesson first (this is the real event being verified).
    progress = await client.post(
        f"/api/v1/lessons/{lesson_id}/progress",
        json={"progress_percent": 100, "completed": True},
    )
    assert progress.status_code == 200, progress.text

    r = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert r.status_code == 200, r.text


async def test_quest_bound_task_rejected_without_a_valid_attempt(client, session):
    await _register(client, "verify_teacher3@ex.com", "teacher")
    quest_resp = await client.post(
        "/api/v1/quests",
        json={"title": "Quest Fisika", "kind": "exam", "opens_at": None, "closes_at": None},
    )
    assert quest_resp.status_code == 201, quest_resp.text
    quest_id = quest_resp.json()["id"]

    task = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Ikuti Quest Fisika",
            "kind": "exam",
            "reward_amount": 20,
            "quest_id": quest_id,
        },
    )
    assert task.status_code == 201, task.text
    assert task.json()["honor_system"] is False
    task_id = task.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "verify_student3@ex.com", "student")

    r = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert r.status_code == 409, r.text
    assert "quest" in r.json()["error"]["message"].lower()


async def test_quest_bound_task_accepted_with_a_valid_attempt(client, session):
    import uuid
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.models.identity import User
    from app.models.quest import QuestAttempt

    await _register(client, "verify_teacher4@ex.com", "teacher")
    quest_resp = await client.post(
        "/api/v1/quests",
        json={"title": "Quest Kimia", "kind": "exam"},
    )
    quest_id = quest_resp.json()["id"]

    task = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Ikuti Quest Kimia",
            "kind": "exam",
            "reward_amount": 20,
            "quest_id": quest_id,
        },
    )
    task_id = task.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "verify_student4@ex.com", "student")

    # Simulate a valid quest attempt directly (the exam-submit path already
    # covers attempt creation elsewhere; here we only need the verification
    # gate to see a row exists).
    user_row = (
        await session.execute(select(User).where(User.email == "verify_student4@ex.com"))
    ).scalar_one()
    session.add(
        QuestAttempt(
            id=uuid.uuid4(),
            quest_id=uuid.UUID(quest_id),
            user_id=user_row.id,
            submitted_at=datetime.now(UTC),
            score_bp=9000,
            is_valid=True,
        )
    )
    await session.commit()

    r = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert r.status_code == 200, r.text


async def test_unbound_task_remains_pure_self_report(client):
    await _register(client, "verify_teacher5@ex.com", "teacher")
    task = await client.post(
        "/api/v1/tasks",
        json={"title": "Baca buku di rumah", "kind": "daily", "reward_amount": 5},
    )
    assert task.status_code == 201, task.text
    assert task.json()["honor_system"] is True
    task_id = task.json()["id"]

    await client.post("/api/v1/auth/logout")
    await _register(client, "verify_student5@ex.com", "student")

    r = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert r.status_code == 200, r.text
