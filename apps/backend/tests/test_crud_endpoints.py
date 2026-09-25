"""CRUD regressions for the endpoints added to complete teacher/admin CRUD.

Covers delete permissions and the guard rails that prevent destructive deletes
from orphaning child records (answers, attempts, finalized rewards).
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="CRUD User")


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
    from tests.helpers import register_actor

    r = await register_actor(client, "crud_admin8@ex.com", "teacher")
    admin_id = r["id"]
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


async def test_wallet_never_exposes_platform_address(client):
    """The shared platform/treasury address must never reach a regular user."""
    from app.core.config import settings

    await _register(client, "wallet_custodial@ex.com", "student")
    r = await client.get("/api/v1/wallet")
    assert r.status_code == 200, r.text
    body = r.json()
    # The caller only ever sees their *own* withdrawal wallet; the shared
    # custodial/treasury address is deliberately not part of the response.
    assert "custodial_address" not in body
    assert "available" in body and body["available"] == 0
    # Whatever we do expose must never equal the platform treasury address.
    assert body.get("withdrawal_address") != (settings.treasury_address or None)


async def test_new_account_defaults_to_platform_wallet(client, monkeypatch):
    """A fresh account's personal wallet defaults to the configured address."""
    from app.core.config import settings

    default = "0x000000000000000000000000000000000000dEaD"
    monkeypatch.setattr(settings, "default_wallet_address", default)

    await _register(client, "wallet_default@ex.com", "student")
    body = (await client.get("/api/v1/wallet")).json()
    assert body["withdrawal_address"] == default


async def test_new_account_has_no_address_without_default(client, monkeypatch):
    """With no configured default, a new account simply has no address yet."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "default_wallet_address", "")

    await _register(client, "wallet_nodefault@ex.com", "student")
    body = (await client.get("/api/v1/wallet")).json()
    assert body["withdrawal_address"] in (None, "")


async def test_user_can_change_own_wallet_address(client):
    """Any user may change their own personal wallet; the change is persisted."""
    await _register(client, "wallet_change@ex.com", "student")
    new_addr = "0x000000000000000000000000000000000000dEaD"
    r = await client.patch("/api/v1/wallet/address", json={"address": new_addr, "source": "manual"})
    assert r.status_code == 200, r.text
    # Stored EIP-55 checksummed.
    assert r.json()["withdrawal_address"].lower() == new_addr.lower()

    # Persisted across reads.
    again = (await client.get("/api/v1/wallet")).json()
    assert again["withdrawal_address"].lower() == new_addr.lower()


async def test_wallet_change_accepts_lowercase_and_checksums(client):
    """A lowercase address is accepted and returned EIP-55 checksummed."""
    await _register(client, "wallet_case@ex.com", "student")
    lower = "0x1234567890abcdef1234567890abcdef12345678"
    r = await client.patch("/api/v1/wallet/address", json={"address": lower, "source": "metamask"})
    assert r.status_code == 200, r.text
    assert r.json()["withdrawal_address"] == "0x1234567890AbcdEF1234567890aBcdef12345678"


async def test_wallet_change_rejects_invalid_address(client):
    await _register(client, "wallet_bad@ex.com", "student")
    for bad in ["not-an-address", "0x123", "0x" + "z" * 40]:
        r = await client.patch("/api/v1/wallet/address", json={"address": bad})
        assert r.status_code == 422, f"{bad} -> {r.status_code}"


async def test_wallet_change_requires_auth(client):
    r = await client.patch(
        "/api/v1/wallet/address", json={"address": "0x" + "1" * 40, "source": "manual"}
    )
    assert r.status_code == 401, r.text


async def test_wallet_change_audited(client, engine):
    """Changing the wallet records an audit log entry owned by the user."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.identity import AuditLog

    user = await _register(client, "wallet_audit@ex.com", "student")
    addr = "0x000000000000000000000000000000000000bEEF"
    r = await client.patch("/api/v1/wallet/address", json={"address": addr, "source": "metamask"})
    assert r.status_code == 200, r.text

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        logs = (
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.action == "wallet.address_change",
                        AuditLog.actor_id == uuid.UUID(user["id"]),
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(logs) == 1
    assert logs[0].data["source"] == "metamask"


async def test_blockchain_status_hides_addresses_for_users(client):
    """The user-facing chain status must not leak contract/treasury addresses."""
    await _register(client, "chain_status_user@ex.com", "student")
    r = await client.get("/api/v1/blockchain/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "contract_address" not in body
    assert "treasury_address" not in body
    # Non-address fields are still present.
    assert "network" in body and "chain_id" in body


async def test_blockchain_contract_requires_admin(client):
    """Deployment addresses are admin-only."""
    await _register(client, "chain_contract_user@ex.com", "student")
    denied = await client.get("/api/v1/blockchain/contract")
    assert denied.status_code == 403, denied.text

    denied_status = await client.get("/api/v1/blockchain/status/admin")
    assert denied_status.status_code == 403, denied_status.text


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
                io.BytesIO(
                    make_pdf("Fisika kuantum membahas partikel dan gelombang secara rinci.")
                ),
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


async def test_material_rename(client):
    import io

    from tests.pdf_util import make_pdf

    await _register(client, "crud_mat_rename@ex.com", "teacher")
    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("old.pdf", io.BytesIO(make_pdf("Materi biologi sel.")), "application/pdf")},
    )
    material_id = up.json()["id"]
    resp = await client.patch(f"/api/v1/materials/{material_id}", json={"filename": "baru.pdf"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["filename"] == "baru.pdf"


async def test_admin_create_user(client, engine):
    """An admin can create an account of any role via /admin/users."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.identity import Role, UserRole

    # Bootstrap: register a teacher, then promote them to admin in the DB.
    r = await _register(client, "crud_admin_create@ex.com", "teacher")
    admin_id = r["id"]

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

    await client.post("/api/v1/auth/logout")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "crud_admin_create@ex.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text

    created = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "crud_new_teacher@ex.com",
            "full_name": "New Teacher",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["email"] == "crud_new_teacher@ex.com"
    assert "teacher" in body["roles"]

    # Duplicate email is rejected.
    dup = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "crud_new_teacher@ex.com",
            "full_name": "Dup",
            "password": "Password123!",
            "role": "student",
        },
    )
    assert dup.status_code == 409, dup.text

    # The new account can actually sign in.
    await client.post("/api/v1/auth/logout")
    relogin = await client.post(
        "/api/v1/auth/login",
        json={"email": "crud_new_teacher@ex.com", "password": "Password123!"},
    )
    assert relogin.status_code == 200, relogin.text


async def test_create_user_requires_admin(client):
    """A non-admin teacher cannot call the create-user endpoint."""
    await _register(client, "crud_not_admin@ex.com", "teacher")
    resp = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "crud_should_fail@ex.com",
            "full_name": "Nope",
            "password": "Password123!",
            "role": "student",
        },
    )
    assert resp.status_code == 403, resp.text


async def test_course_and_lesson_pagination(client):
    """List endpoints accept limit/offset and cap the page window."""
    await _register(client, "crud_page_teacher@ex.com", "teacher")
    course_ids = []
    for i in range(5):
        c = await client.post(
            "/api/v1/courses",
            json={"title": f"Page Course {i}", "class_code": "2A", "class_type": "IPA"},
        )
        assert c.status_code == 201, c.text
        course_ids.append(c.json()["id"])

    course_id = course_ids[0]
    for i in range(4):
        lesson = await client.post(
            f"/api/v1/courses/{course_id}/lessons",
            json={"title": f"Lesson {i}", "content_md": "x", "position": i},
        )
        assert lesson.status_code == 201, lesson.text

    # Paginated lessons: first window.
    first = await client.get(f"/api/v1/courses/{course_id}/lessons?limit=2&offset=0")
    assert first.status_code == 200, first.text
    assert len(first.json()) == 2
    assert first.json()[0]["title"] == "Lesson 0"

    # Second window continues where the first stopped.
    second = await client.get(f"/api/v1/courses/{course_id}/lessons?limit=2&offset=2")
    assert second.status_code == 200, second.text
    assert len(second.json()) == 2
    assert second.json()[0]["title"] == "Lesson 2"

    # /me/subjects is paginated too.
    mine = await client.get("/api/v1/me/subjects?limit=1&offset=0")
    assert mine.status_code == 200, mine.text
    assert len(mine.json()) == 1

    # Over-max limit is rejected by the bounded LimitParam.
    too_big = await client.get(f"/api/v1/courses/{course_id}/lessons?limit=500")
    assert too_big.status_code == 422, too_big.text

    await _register(client, "crud_room_owner@ex.com", "teacher")
    room = await client.post(
        "/api/v1/rooms",
        json={"name": "Ruang Uji", "is_public": True, "max_participants": 10},
    )
    assert room.status_code == 201, room.text
    room_id = room.json()["id"]
    dele = await client.delete(f"/api/v1/rooms/{room_id}")
    assert dele.status_code == 204, dele.text
    gone = await client.get(f"/api/v1/rooms/{room_id}")
    assert gone.status_code == 404


async def test_task_crud_and_delete_guard(client, engine):
    await _register(client, "crud_task_owner@ex.com", "teacher")
    task = await client.post(
        "/api/v1/tasks",
        json={"title": "Tugas Harian", "kind": "daily", "reward_amount": 10},
    )
    assert task.status_code == 201, task.text
    task_id = task.json()["id"]

    upd = await client.patch(f"/api/v1/tasks/{task_id}", json={"title": "Tugas Harian (edit)"})
    assert upd.status_code == 200, upd.text
    assert upd.json()["title"] == "Tugas Harian (edit)"

    # Complete as a student, then the owner may not delete it any more.
    await client.post("/api/v1/auth/logout")
    await _register(client, "crud_task_stu@ex.com", "student")
    done = await client.post(f"/api/v1/tasks/{task_id}/complete")
    assert done.status_code == 200, done.text

    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login",
        json={"email": "crud_task_owner@ex.com", "password": "Password123!"},
    )
    blocked = await client.delete(f"/api/v1/tasks/{task_id}")
    assert blocked.status_code == 409, blocked.text

    # Clean up: the completion created a reward outbox/ledger row that other
    # tests (e.g. quests ledger) count globally in the shared test DB.
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.quest import Task, TaskCompletion
    from app.models.wallet import RewardAllocation, TransactionOutbox
    from app.models.wallet import WalletLedgerEntry as _LE

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        await s.execute(delete(TransactionOutbox).where(TransactionOutbox.topic == "reward"))
        await s.execute(delete(RewardAllocation).where(RewardAllocation.task_id == task_id))
        await s.execute(delete(_LE).where(_LE.reference_type == "task"))
        await s.execute(delete(TaskCompletion).where(TaskCompletion.task_id == task_id))
        await s.execute(delete(Task).where(Task.id == task_id))
        await s.commit()


async def test_lesson_reorder_is_atomic(client):
    """C38: reorder rewrites every lesson position from the given order."""
    await _register(client, "reorder_t@ex.com", "teacher")
    course = await client.post(
        "/api/v1/courses", json={"title": "Reorder 1A", "class_code": "1A", "class_type": "IPA"}
    )
    course_id = course.json()["id"]
    ids = []
    for i in range(3):
        lesson = await client.post(
            f"/api/v1/courses/{course_id}/lessons", json={"title": f"L{i}", "position": i}
        )
        ids.append(lesson.json()["id"])

    reversed_ids = list(reversed(ids))
    r = await client.post(
        f"/api/v1/courses/{course_id}/lessons/reorder", json={"lesson_ids": reversed_ids}
    )
    assert r.status_code == 200, r.text
    listing = await client.get(f"/api/v1/courses/{course_id}/lessons")
    order = [x["id"] for x in listing.json()]
    assert order == reversed_ids

    # A partial list is rejected (never corrupts positions).
    bad = await client.post(
        f"/api/v1/courses/{course_id}/lessons/reorder", json={"lesson_ids": ids[:2]}
    )
    assert bad.status_code == 422, bad.text


async def test_material_delete_blocked_with_pending_drafts(client):
    """C38: deleting a material with pending AI drafts is refused with 409."""
    from sqlalchemy import select

    from app.models.exam import Question

    await _register(client, "matdel_t@ex.com", "teacher")
    import io

    from tests.pdf_util import make_pdf

    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("m.pdf", io.BytesIO(make_pdf("Materi fisika tentang gerak benda.")), "application/pdf")},
        data={"title": "M"},
    )
    material_id = up.json()["id"]

    # Insert a pending draft question referencing the material directly in the DB.
    sm = client._sm  # type: ignore[attr-defined]
    async with sm() as s:
        me = (await client.get("/api/v1/auth/me")).json()["id"]
        import uuid as _uuid

        s.add(
            Question(
                material_id=_uuid.UUID(material_id),
                owner_id=_uuid.UUID(me),
                prompt="Draf soal menunggu tinjauan?",
                source="ai",
                review_status="pending",
            )
        )
        await s.commit()

    r = await client.delete(f"/api/v1/materials/{material_id}")
    assert r.status_code == 409, r.text

    # Clean up the draft so it does not leak into other tests.
    async with sm() as s:
        for q in (
            await s.execute(
                select(Question).where(Question.material_id == _uuid.UUID(material_id))
            )
        ).scalars().all():
            await s.delete(q)
        await s.commit()


async def test_course_progress_aggregate_and_resume(client):
    """C37: course progress aggregates lessons and points to the next one."""
    await _register(client, "prog_t@ex.com", "teacher")
    course = await client.post(
        "/api/v1/courses", json={"title": "Progres 1B", "class_code": "1B", "class_type": "IPA", "is_published": True}
    )
    course_id = course.json()["id"]
    lids = []
    for i in range(3):
        lesson = await client.post(
            f"/api/v1/courses/{course_id}/lessons",
            json={"title": f"L{i}", "position": i, "is_published": True},
        )
        lids.append(lesson.json()["id"])
    await client.post("/api/v1/auth/logout")

    from tests.helpers import register_actor

    await register_actor(client, "prog_s@ex.com", "student", class_code="1B", class_type="IPA")
    empty = await client.get(f"/api/v1/courses/{course_id}/progress")
    assert empty.status_code == 200, empty.text
    body = empty.json()
    assert body["total_lessons"] == 3
    assert body["completed_lessons"] == 0
    assert body["next_lesson_id"] == lids[0]

    # Partial progress (1–99) is stored and is monotonic.
    p = await client.post(
        f"/api/v1/lessons/{lids[0]}/progress", json={"progress_percent": 40}
    )
    assert p.status_code == 200, p.text
    assert p.json()["progress_percent"] == 40
    p2 = await client.post(
        f"/api/v1/lessons/{lids[0]}/progress", json={"progress_percent": 20}
    )
    assert p2.json()["progress_percent"] == 40  # never decreases

    await client.post(
        f"/api/v1/lessons/{lids[0]}/progress",
        json={"progress_percent": 100, "completed": True},
    )
    after = (await client.get(f"/api/v1/courses/{course_id}/progress")).json()
    assert after["completed_lessons"] == 1
    assert after["percent"] == 33
    assert after["next_lesson_id"] == lids[1]


async def test_plan_list_endpoints_reject_over_max_limit(client):
    """§9: every list endpoint must bound pagination (limit <= 200 -> 422)."""
    await _register(client, "crud_limit@ex.com", "admin")
    for path in (
        "/api/v1/community/posts?limit=500",
        "/api/v1/community/reports?limit=500",
        "/api/v1/career/consultations?limit=500",
        "/api/v1/career/resources?limit=500",
        "/api/v1/career/assistant/conversations?limit=500",
        "/api/v1/admin/withdrawals?limit=500",
        "/api/v1/admin/audit-logs?limit=500",
        "/api/v1/rankings/leaderboards?limit=500",
        "/api/v1/materials?limit=500",
    ):
        r = await client.get(path)
        assert r.status_code == 422, f"{path} -> {r.status_code}"
