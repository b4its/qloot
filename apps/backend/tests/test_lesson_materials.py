"""Student-visible material listing per lesson (C33)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.learning import CourseMember
from tests.pdf_util import make_pdf

pytestmark = pytest.mark.integration


async def _make_course_lesson_material(client, *, code="1A") -> tuple[str, str, str]:
    course = await client.post(
        "/api/v1/courses",
        json={
            "title": f"Kelas Materi {code}",
            "class_code": code,
            "class_type": "IPA",
            "is_published": True,
        },
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]
    lesson = await client.post(
        f"/api/v1/courses/{course_id}/lessons", json={"title": "Pertemuan 1", "position": 0}
    )
    lesson_id = lesson.json()["id"]
    files = {
        "file": ("m.pdf", make_pdf("Materi fisika kelas 1A tentang gerak."), "application/pdf")
    }
    up = await client.post(
        "/api/v1/materials/upload",
        files=files,
        data={"lesson_id": lesson_id, "course_id": course_id},
    )
    assert up.status_code == 201, up.text
    return course_id, lesson_id, up.json()["id"]


async def test_member_lists_lesson_materials_and_non_member_403(make_actor, engine):
    teacher = await make_actor("lm_teacher@ex.com", "teacher")
    course_id, lesson_id, material_id = await _make_course_lesson_material(teacher.client)

    student = await make_actor("lm_student@ex.com", "student")
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        s.add(CourseMember(course_id=uuid.UUID(course_id), user_id=uuid.UUID(student.user["id"])))
        await s.commit()

    # Member sees the material.
    r = await student.client.get(f"/api/v1/lessons/{lesson_id}/materials")
    assert r.status_code == 200, r.text
    ids = [m["id"] for m in r.json()]
    assert material_id in ids

    # A student who is NOT a member gets 403 (or 404 if the lesson is invisible).
    outsider = await make_actor("lm_outsider@ex.com", "student")
    r2 = await outsider.client.get(f"/api/v1/lessons/{lesson_id}/materials")
    assert r2.status_code in (403, 404), r2.text


async def test_teacher_owner_always_sees_lesson_materials(make_actor):
    teacher = await make_actor("lm2_teacher@ex.com", "teacher")
    _course_id, lesson_id, material_id = await _make_course_lesson_material(
        teacher.client, code="2B"
    )
    r = await teacher.client.get(f"/api/v1/lessons/{lesson_id}/materials")
    assert r.status_code == 200, r.text
    assert material_id in [m["id"] for m in r.json()]


async def test_unknown_lesson_is_404(make_actor):
    student = await make_actor("lm3_student@ex.com", "student")
    r = await student.client.get(f"/api/v1/lessons/{uuid.uuid4()}/materials")
    assert r.status_code == 404, r.text
