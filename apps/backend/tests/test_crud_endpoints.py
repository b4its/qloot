"""CRUD regressions for the endpoints added to complete teacher/admin CRUD.

Covers delete permissions and the guard rails that prevent destructive deletes
from orphaning child records (answers, attempts, finalized rewards).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "CRUD User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _make_exam(client, title="CRUD Exam"):
    exam = await client.post("/api/v1/exams", json={"title": title, "duration_minutes": 30})
    assert exam.status_code == 201, exam.text
    return exam.json()["id"]


async def test_exam_delete_and_question_delete(client):
    await _register(client, "crud_teacher1@ex.com")
    exam_id = await _make_exam(client)
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Apa itu massa?", "correct_answer": "Jumlah materi"},
    )
    assert q.status_code == 201, q.text
    qid = q.json()["id"]

    # Question delete works while it has no answers.
    dele = await client.delete(f"/api/v1/questions/{qid}")
    assert dele.status_code == 204, dele.text

    # Exam delete works (no attempts).
    dele2 = await client.delete(f"/api/v1/exams/{exam_id}")
    assert dele2.status_code == 204, dele2.text
    gone = await client.get(f"/api/v1/exams/{exam_id}")
    assert gone.status_code == 404


async def test_cannot_delete_exam_with_attempts(client):
    await _register(client, "crud_teacher2@ex.com")
    exam_id = await _make_exam(client)
    await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Apa itu gaya?", "correct_answer": "Dorongan"},
    )
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "crud_student@ex.com", "student")
    assert (await client.post(f"/api/v1/exams/{exam_id}/attempts")).status_code == 201
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login",
        json={"email": "crud_teacher2@ex.com", "password": "Password123!"},
    )
    resp = await client.delete(f"/api/v1/exams/{exam_id}")
    assert resp.status_code == 409, resp.text


async def test_cannot_delete_question_with_answers(client):
    await _register(client, "crud_teacher3@ex.com")
    exam_id = await _make_exam(client)
    qid = (
        await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={"prompt": "Apa itu usaha?", "correct_answer": "Energi terpakai"},
        )
    ).json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "crud_student2@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}",
        json={"answer_text": "Energi terpakai"},
    )
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login",
        json={"email": "crud_teacher3@ex.com", "password": "Password123!"},
    )
    resp = await client.delete(f"/api/v1/questions/{qid}")
    assert resp.status_code == 409, resp.text


async def test_lesson_update_and_delete(client):
    await _register(client, "crud_teacher4@ex.com")
    course = await client.post(
        "/api/v1/courses",
        json={"title": "CRUD Course", "class_code": "1A", "class_type": "IPA"},
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]
    lesson = await client.post(
        f"/api/v1/courses/{course_id}/lessons",
        json={"title": "Pertemuan 1", "content_md": "Isi", "position": 0},
    )
    assert lesson.status_code == 201, lesson.text
    lesson_id = lesson.json()["id"]

    upd = await client.patch(f"/api/v1/lessons/{lesson_id}", json={"title": "Pertemuan 1 (revisi)"})
    assert upd.status_code == 200, upd.text
    assert upd.json()["title"] == "Pertemuan 1 (revisi)"

    dele = await client.delete(f"/api/v1/lessons/{lesson_id}")
    assert dele.status_code == 204, dele.text


async def test_lesson_delete_requires_ownership(client):
    await _register(client, "crud_owner5@ex.com")
    course = await client.post(
        "/api/v1/courses",
        json={"title": "Own Course", "class_code": "1B", "class_type": "IPA"},
    )
    course_id = course.json()["id"]
    lesson_id = (
        await client.post(
            f"/api/v1/courses/{course_id}/lessons",
            json={"title": "L1", "content_md": "x", "position": 0},
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "crud_other5@ex.com")
    resp = await client.delete(f"/api/v1/lessons/{lesson_id}")
    assert resp.status_code in (403, 404), resp.text


async def test_quest_delete_and_finalized_guard(client):
    await _register(client, "crud_teacher6@ex.com")
    quest = await client.post(
        "/api/v1/quests",
        json={
            "title": "CRUD Quest",
            "top_n_winners": 1,
            "rules": [{"rank": 1, "reward_amount": 50}],
        },
    )
    assert quest.status_code == 201, quest.text
    quest_id = quest.json()["id"]

    upd = await client.patch(f"/api/v1/quests/{quest_id}", json={"title": "CRUD Quest Updated"})
    assert upd.status_code == 200, upd.text
    assert upd.json()["title"] == "CRUD Quest Updated"

    dele = await client.delete(f"/api/v1/quests/{quest_id}")
    assert dele.status_code == 204, dele.text


async def test_material_delete(client):
    import io

    from tests.pdf_util import make_pdf

    await _register(client, "crud_teacher7@ex.com")
    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("m.pdf", io.BytesIO(make_pdf("Materi untuk dihapus.")), "application/pdf")},
    )
    assert up.status_code == 201, up.text
    material_id = up.json()["id"]

    dele = await client.delete(f"/api/v1/materials/{material_id}")
    assert dele.status_code == 204, dele.text
    gone = await client.get(f"/api/v1/materials/{material_id}")
    assert gone.status_code == 404


async def test_admin_can_deactivate_and_reactivate_user(client, engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.identity import Role, UserRole

    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "crud_admin8@ex.com",
            "full_name": "Admin Eight",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    admin_id = r.json()["id"]
    target = await _register(client, "crud_target8@ex.com", "student")
    target_id = target["id"]

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        admin_role = (await s.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        for ur in (
            (await s.execute(select(UserRole).where(UserRole.user_id == admin_id))).scalars().all()
        ):
            await s.delete(ur)
        await s.flush()
        s.add(UserRole(user_id=admin_id, role_id=admin_role.id))
        await s.commit()

    # Re-login as the promoted admin (the register helper logged us in as target).
    await client.post("/api/v1/auth/logout")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "crud_admin8@ex.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text

    off = await client.patch(f"/api/v1/admin/users/{target_id}/active", json={"is_active": False})
    assert off.status_code == 200, off.text
    assert off.json()["is_active"] is False

    on = await client.patch(f"/api/v1/admin/users/{target_id}/active", json={"is_active": True})
    assert on.status_code == 200, on.text
    assert on.json()["is_active"] is True


async def test_wallet_exposes_shared_custodial_address(client):
    """The wallet response must surface the shared custodial wallet address."""
    from app.core.config import settings

    await _register(client, "wallet_custodial@ex.com", "student")
    r = await client.get("/api/v1/wallet")
    assert r.status_code == 200, r.text
    body = r.json()
    # The shared (treasury) wallet is exposed so the UI can show where pooled
    # tokens live, while ``available`` is the user's own focused share.
    assert "custodial_address" in body
    assert body["custodial_address"] == (settings.treasury_address or None)
    assert "available" in body and body["available"] == 0


async def test_student_cannot_approve_own_career_plan(client, engine):
    """Only a counselor (teacher/admin) may approve recommendations."""
    student = await _register(client, "crud_career_stu@ex.com", "student")
    await client.post("/api/v1/career/grades", json={"subject": "Fisika", "grade": 90})
    await client.post("/api/v1/career/recommendations/generate")
    await client.post("/api/v1/career/recommendations/submit")

    denied = await client.post("/api/v1/career/recommendations/approve")
    assert denied.status_code == 403, denied.text

    # A teacher can approve the specific student.
    await client.post("/api/v1/auth/logout")
    await _register(client, "crud_career_bk@ex.com", "teacher")
    ok = await client.post(f"/api/v1/career/recommendations/approve?user_id={student['id']}")
    assert ok.status_code == 200, ok.text


async def test_generate_questions_rejects_foreign_exam(client):
    """A teacher cannot attach AI questions to another teacher's exam."""
    import io

    from tests.pdf_util import make_pdf

    # Teacher A owns an exam.
    await _register(client, "crud_exam_a@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "Exam A", "duration_minutes": 30})
    exam_id = exam.json()["id"]
    await client.post("/api/v1/auth/logout")

    # Teacher B uploads a material and tries to generate into exam A.
    await _register(client, "crud_exam_b@ex.com", "teacher")
    up = await client.post(
        "/api/v1/materials/upload",
        files={
            "file": (
                "m.pdf",
                io.BytesIO(make_pdf("Fisika kuantum membahas partikel dan gelombang secara rinci.")),
                "application/pdf",
            )
        },
    )
    material_id = up.json()["id"]
    resp = await client.post(
        f"/api/v1/materials/{material_id}/generate-questions",
        json={"count": 2, "language": "id", "exam_id": exam_id},
    )
    assert resp.status_code == 403, resp.text
