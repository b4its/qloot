"""Regression tests for the 'complete every feature' pass, round 2.

Covers the async/blockchain completeness gaps:
  - swap / ai_request debits are refunded when the on-chain step fails
  - unknown outbox topics are reaped (never silently stuck pending)
  - grading_failed attempts can be re-queued via POST /attempts/{id}/regrade
  - draft AI questions are listable via GET /materials/{id}/questions
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.blockchain.worker_logic import reap_unknown_topics
from app.models.wallet import TransactionOutbox
from app.services.reward_engine import RewardEngine

pytestmark = pytest.mark.integration


async def _mk_user(session, email):
    from sqlalchemy.orm import selectinload

    from app.core.security import hash_password
    from app.models import User
    from app.models.identity import Role, UserRole

    role = (await session.execute(select(Role).where(Role.name == "student"))).scalar_one()
    u = User(
        email=email,
        full_name="T",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + (uuid.uuid4().hex + uuid.uuid4().hex)[:64],
    )
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role.id))
    await session.flush()
    return (
        await session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == u.id)
        )
    ).scalar_one()


async def test_refund_swap_returns_opt_and_claws_back_asset(session):
    student = await _mk_user(session, "swap_refund@q.com")
    engine = RewardEngine(session)
    # Seed 100 OPT, then debit 30 OPT + credit 10 QTC (as a successful swap).
    await engine.credit(
        user=student,
        amount=100,
        reference_type="seed",
        reference_id="seed-swap",
        reward_key_value="",
        token_id=0,
    )
    await engine.debit_for_withdrawal(
        user=student, amount=30, withdrawal_id=uuid.uuid4(), destination="ORX:QTC"
    )
    await engine.credit_asset(user_id=student.id, asset="QTC", amount=10)
    assert await engine.balance(student.id) == 70
    assert await engine.asset_balance(student.id, "QTC") == 10

    # The swap fails on-chain: OPT is returned, QTC clawed back.
    await engine.refund_swap(
        user_id=student.id, opt_cost=30, asset="QTC", asset_amount=10, swap_key="swap-key-1"
    )
    assert await engine.balance(student.id) == 100
    assert await engine.asset_balance(student.id, "QTC") == 0

    # Idempotent: a second refund for the same key must not double-credit OPT.
    await engine.refund_swap(
        user_id=student.id, opt_cost=30, asset="QTC", asset_amount=10, swap_key="swap-key-1"
    )
    assert await engine.balance(student.id) == 100


async def test_refund_ai_request_returns_ort(session):
    student = await _mk_user(session, "ai_refund@q.com")
    engine = RewardEngine(session)
    await engine.credit_asset(user_id=student.id, asset="ORT", amount=5)
    await engine.debit_asset(user_id=student.id, asset="ORT", amount=3)
    assert await engine.asset_balance(student.id, "ORT") == 2

    await engine.refund_ai_request(user_id=student.id, requests=3)
    assert await engine.asset_balance(student.id, "ORT") == 5


async def test_reap_unknown_topics_marks_failed(session):
    student = await _mk_user(session, "reap@q.com")
    session.add(
        TransactionOutbox(
            topic="totally_unknown",
            idempotency_key="unknown-topic-key",
            payload={"user_id": str(student.id)},
            status="pending",
        )
    )
    await session.flush()

    reaped = await reap_unknown_topics(session, ("reward", "withdrawal", "swap"))
    assert reaped >= 1
    row = (
        await session.execute(
            select(TransactionOutbox).where(
                TransactionOutbox.idempotency_key == "unknown-topic-key"
            )
        )
    ).scalar_one()
    assert row.status == "failed"
    assert row.last_error and "Unknown outbox topic" in row.last_error


# --- HTTP-level ----------------------------------------------------------
async def _register(client, email, role="teacher"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Round2 User")


async def test_regrade_requeues_failed_attempt(client):
    """A grading_failed attempt can be re-queued (not permanently stuck)."""
    await _register(client, "regrade_teacher@ex.com")
    exam = await client.post(
        "/api/v1/exams", json={"title": "Regrade Exam", "duration_minutes": 10}
    )
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Ibu kota Indonesia?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [
                {"text": "Jakarta", "is_correct": True},
                {"text": "Bandung", "is_correct": False},
            ],
        },
    )
    qid = q.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    # A student submits, then we force the attempt into grading_failed.
    await _register(client, "regrade_student@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await client.post("/api/v1/auth/logout")

    from app.db.session import get_sessionmaker

    sm = get_sessionmaker()
    from app.models.exam import ExamAttempt

    async with sm() as s:
        att = await s.get(ExamAttempt, uuid.UUID(attempt_id))
        att.status = "grading_failed"
        await s.commit()

    await client.post(
        "/api/v1/auth/login", json={"email": "regrade_teacher@ex.com", "password": "Password123!"}
    )
    reg = await client.post(f"/api/v1/attempts/{attempt_id}/regrade")
    assert reg.status_code == 200, reg.text
    # The MC-only exam is graded inline, so it is 'graded' again after regrade.
    assert reg.json()["status"] == "graded"


async def test_regrade_rejects_graded_attempt(client):
    await _register(client, "regrade2_teacher@ex.com")
    exam = await client.post("/api/v1/exams", json={"title": "Regrade2", "duration_minutes": 10})
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "2 + 2?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [
                {"text": "4", "is_correct": True},
                {"text": "5", "is_correct": False},
            ],
        },
    )
    qid = q.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")
    await _register(client, "regrade2_student@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login", json={"email": "regrade2_teacher@ex.com", "password": "Password123!"}
    )
    # Already graded => 409 (no re-grade of a healthy attempt).
    reg = await client.post(f"/api/v1/attempts/{attempt_id}/regrade")
    assert reg.status_code == 409, reg.text


async def test_material_draft_questions_listable(client):
    """AI-generated (pending) questions are reachable via the material."""
    from tests.pdf_util import make_pdf

    await _register(client, "r2_mat_owner@ex.com")
    up = await client.post(
        "/api/v1/materials/upload",
        files={
            "file": (
                "m.pdf",
                make_pdf("Materi tentang fotosintesis dan klorofil pada tumbuhan."),
                "application/pdf",
            )
        },
    )
    assert up.status_code == 201, up.text
    material_id = up.json()["id"]
    gen = await client.post(
        f"/api/v1/materials/{material_id}/generate-questions-sync",
        json={"count": 2, "language": "id"},
    )
    assert gen.status_code == 200, gen.text
    assert len(gen.json()) >= 1

    # The same questions are listable from the material (not orphaned).
    listed = await client.get(f"/api/v1/materials/{material_id}/questions")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body) == len(gen.json())
    assert all("prompt" in q and "review_status" in q for q in body)


async def test_material_questions_requires_owner(client):
    from tests.pdf_util import make_pdf

    await _register(client, "mat_owner2@ex.com")
    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("m.pdf", make_pdf("Materi rahasia fisika kuantum."), "application/pdf")},
    )
    material_id = up.json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "r2_mat_other@ex.com")
    denied = await client.get(f"/api/v1/materials/{material_id}/questions")
    assert denied.status_code in (403, 404), denied.text
