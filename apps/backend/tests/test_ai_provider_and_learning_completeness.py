"""Regression tests for the 'complete every feature' pass, round 5.

Covers the AI-provider fail-fast, reward-retry ledger consistency, course/lesson
visibility, and other hardening:
  - a real AI provider selected without its API key fails fast (never silently
    falls back to the mock, which would fabricate grades)
  - provider_name() records the real model for audit
  - admin user creation leaves no orphan session
  - retrying a failed reward restores the ledger credit
  - draft lessons are hidden from students; approved AI questions drop out of
    the material draft list
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "R5 User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- AI provider fail-fast ------------------------------------------------
def test_openai_without_key_raises(monkeypatch):
    from app.ai import provider as prov
    from app.core.config import settings
    from app.core.errors import AIProviderError

    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "ai_api_key", "")
    prov._provider = None
    with pytest.raises(AIProviderError):
        prov.get_ai_provider()
    prov._provider = None


def test_gemini_without_key_raises(monkeypatch):
    from app.ai import provider as prov
    from app.core.config import settings
    from app.core.errors import AIProviderError

    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    prov._provider = None
    with pytest.raises(AIProviderError):
        prov.get_ai_provider()
    prov._provider = None


def test_mock_provider_name_and_selection(monkeypatch):
    from app.ai import provider as prov
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "mock")
    prov._provider = None
    p = prov.get_ai_provider()
    assert isinstance(p, prov.MockProvider)
    assert prov.provider_name() == "mock"
    prov._provider = None


# --- admin create_user leaves no orphan session ---------------------------
async def test_admin_created_user_has_no_session(client):
    from sqlalchemy import func, select

    from app.db.session import get_sessionmaker
    from app.models.identity import Session as SessionModel

    admin = await _register(client, "r5_admin@ex.com", "teacher")
    # Promote to admin directly (registration cannot self-assign admin).
    from app.db.session import get_sessionmaker as _sm

    sm = _sm()
    async with sm() as s:
        from app.models.identity import Role, UserRole

        role = (await s.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        s.add(UserRole(user_id=uuid.UUID(admin["id"]), role_id=role.id))
        await s.commit()
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login", json={"email": "r5_admin@ex.com", "password": "Password123!"}
    )
    created = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "r5_created@ex.com",
            "full_name": "Created",
            "password": "Password123!",
            "role": "student",
        },
    )
    assert created.status_code == 201, created.text
    new_id = uuid.UUID(created.json()["id"])

    sm = get_sessionmaker()
    async with sm() as s:
        n = (
            await s.execute(
                select(func.count()).select_from(SessionModel).where(SessionModel.user_id == new_id)
            )
        ).scalar_one()
    assert int(n) == 0


# --- retry restores the ledger credit -------------------------------------
async def test_retry_reward_recredits_after_failure(session):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.security import hash_password
    from app.models import Quest, User
    from app.models.identity import Role, UserRole
    from app.models.wallet import RewardAllocation
    from app.services.reward_engine import RewardEngine

    role = (await session.execute(select(Role).where(Role.name == "student"))).scalar_one()
    owner = User(
        email="rr_owner@q.com",
        full_name="O",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
    )
    student = User(
        email="rr_student@q.com",
        full_name="S",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
    )
    session.add_all([owner, student])
    await session.flush()
    session.add(UserRole(user_id=student.id, role_id=role.id))
    await session.flush()
    student = (
        await session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == student.id)
        )
    ).scalar_one()

    quest = Quest(title="Q", owner_id=owner.id, status="open", top_n_winners=1)
    session.add(quest)
    await session.flush()
    engine = RewardEngine(session)
    alloc = await engine.allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    assert await engine.balance(student.id) == 100

    # Simulate a failed on-chain mint: the reward is refunded (balance back to 0).
    await engine.refund_reward(user_id=student.id, amount=100, allocation_id=alloc.id)
    alloc.status = "failed"
    await session.flush()
    assert await engine.balance(student.id) == 0

    # Retry re-credits the user so the ledger stays consistent.
    await engine.recredit_reward_retry(user_id=student.id, amount=100, allocation_id=alloc.id)
    await session.flush()
    assert await engine.balance(student.id) == 100
    # Idempotent.
    await engine.recredit_reward_retry(user_id=student.id, amount=100, allocation_id=alloc.id)
    await session.flush()
    assert await engine.balance(student.id) == 100
    _ = RewardAllocation


# --- draft lessons hidden from students -----------------------------------
async def test_draft_lesson_hidden_from_student(client):
    # Teacher creates a published subject with a draft + a published lesson.
    await _register(client, "r5_teacher@ex.com")
    course = await client.post(
        "/api/v1/courses",
        json={"title": "Fisika 1A", "class_code": "1A", "class_type": "IPA", "is_published": True},
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]
    published = await client.post(
        f"/api/v1/courses/{course_id}/lessons",
        json={"title": "Terbit", "content": "A", "position": 0, "is_published": True},
    )
    assert published.status_code == 201, published.text
    draft = await client.post(
        f"/api/v1/courses/{course_id}/lessons",
        json={"title": "Draf", "content": "B", "position": 1, "is_published": False},
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]
    await client.post("/api/v1/auth/logout")

    # Student in class 1A/IPA sees only the published lesson.
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "r5_student@ex.com",
            "full_name": "Student Lima",
            "password": "Password123!",
            "role": "student",
            "class_code": "1A",
            "class_type": "IPA",
        },
    )
    assert reg.status_code == 201, reg.text
    lessons = await client.get(f"/api/v1/courses/{course_id}/lessons")
    assert lessons.status_code == 200, lessons.text
    titles = [lesson["title"] for lesson in lessons.json()]
    assert "Terbit" in titles and "Draf" not in titles
    # Direct fetch of the draft 404s for the student.
    assert (await client.get(f"/api/v1/lessons/{draft_id}")).status_code == 404


# --- material draft list excludes approved --------------------------------
async def test_material_draft_list_excludes_approved(client):
    from tests.pdf_util import make_pdf

    await _register(client, "r5_mat@ex.com")
    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("m.pdf", make_pdf("Materi tentang fisika dan energi."), "application/pdf")},
    )
    material_id = up.json()["id"]
    gen = await client.post(
        f"/api/v1/materials/{material_id}/generate-questions-sync",
        json={"count": 2, "language": "id"},
    )
    assert gen.status_code == 200, gen.text
    qid = gen.json()[0]["id"]

    drafts = await client.get(f"/api/v1/materials/{material_id}/questions")
    assert any(q["id"] == qid for q in drafts.json())

    # Approve it => it drops out of the draft list.
    await client.patch(f"/api/v1/questions/{qid}", json={"review_status": "approved"})
    after = await client.get(f"/api/v1/materials/{material_id}/questions")
    assert all(q["id"] != qid for q in after.json())
