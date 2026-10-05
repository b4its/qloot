"""Regression tests proving and guarding against concurrency & logic race conditions:
1. Withdrawal double-spend / free-money race condition (approve vs cancel).
2. Free-tier AI quota bypass via concurrent requests.
3. Counselor consultation slot double-booking conflict.
4. Quest attempt concurrent submission idempotency (no 500 IntegrityError).
5. Exam attempt submission concurrency serialization.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.errors import ConflictError, PaymentRequiredError
from app.models.exam import Exam, ExamAttempt
from app.models.identity import Role, User, UserRole
from app.models.wallet import TransactionOutbox, WalletLedgerEntry
from app.services.ai_usage_service import AiUsageService
from app.services.exam_service import ExamService
from app.services.quest_service import QuestService
from app.services.reward_engine import RewardEngine
from app.services.withdrawal_service import WithdrawalService
from tests.helpers import register_actor

pytestmark = pytest.mark.integration

DEST = "0x" + "2" * 40


async def _seed_user(engine, email: str, role_name: str = "student") -> uuid.UUID:
    from app.core.security import hash_password

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        role = (await s.execute(select(Role).where(Role.name == role_name))).scalar_one()
        u = User(
            email=email,
            full_name=email.split("@")[0].upper(),
            password_hash=hash_password("Password123!"),
            chain_user_ref="0x" + uuid.uuid4().hex + uuid.uuid4().hex,
        )
        s.add(u)
        await s.flush()
        s.add(UserRole(user_id=u.id, role_id=role.id))
        await s.commit()
        return u.id


async def _credit_opt(engine, user_id: uuid.UUID, amount: int) -> None:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        user = await s.get(User, user_id)
        assert user is not None
        await RewardEngine(s).credit(
            user=user,
            amount=amount,
            reference_type="reward",
            reference_id=f"seed-{user_id}-{uuid.uuid4().hex[:6]}",
            reward_key_value=f"rk-{user_id}-{uuid.uuid4().hex[:6]}",
            token_id=0,
        )
        await s.commit()


async def test_withdrawal_concurrent_approve_vs_cancel_prevents_double_spend(engine):
    """When an admin approves and a user cancels concurrently on the SAME withdrawal:
    - Exactly one must succeed.
    - The other must fail with ConflictError.
    - NEVER both: if cancelled, no outbox row must exist; if approved, no refund ledger must exist.
    """
    student_id = await _seed_user(engine, f"std_race_{uuid.uuid4().hex[:6]}@ex.com", "student")
    admin_id = await _seed_user(engine, f"adm_race_{uuid.uuid4().hex[:6]}@ex.com", "admin")

    await _credit_opt(engine, student_id, 500)

    sm = async_sessionmaker(engine, expire_on_commit=False)
    # 1. Student requests withdrawal of 100 OPT
    async with sm() as s:
        student = await s.get(User, student_id)
        assert student is not None
        wd = await WithdrawalService(s).request(
            user=student,
            amount=100,
            destination=DEST,
        )
        wd_id = wd.id
        await s.commit()

    # 2. Concurrently execute approve() in Session A and cancel() in Session B
    async def do_approve():
        async with sm() as sa:
            adm = await sa.get(User, admin_id)
            assert adm is not None
            try:
                await WithdrawalService(sa).approve(admin=adm, withdrawal_id=wd_id)
                await sa.commit()
                return "approved"
            except ConflictError:
                await sa.rollback()
                return "conflict_approve"

    async def do_cancel():
        async with sm() as sb:
            std = await sb.get(User, student_id)
            assert std is not None
            try:
                await WithdrawalService(sb).cancel(user=std, withdrawal_id=wd_id)
                await sb.commit()
                return "cancelled"
            except ConflictError:
                await sb.rollback()
                return "conflict_cancel"

    try:
        results = await asyncio.gather(do_approve(), do_cancel())

        # Exactly one succeeded, exactly one was rejected with ConflictError
        assert set(results) in (
            {"approved", "conflict_cancel"},
            {"cancelled", "conflict_approve"},
        ), f"Unexpected race outcome: {results}"

        # Verify database state consistency (no double spend!)
        from app.services.keys import tx_idempotency_key
        expected_outbox_key = tx_idempotency_key("withdrawal", str(wd_id))

        async with sm() as s:
            outbox_rows = (
                await s.execute(
                    select(TransactionOutbox).where(
                        TransactionOutbox.topic == "withdrawal",
                        TransactionOutbox.idempotency_key == expected_outbox_key,
                    )
                )
            ).scalars().all()

            refund_rows = (
                await s.execute(
                    select(WalletLedgerEntry).where(
                        WalletLedgerEntry.reference_type == "withdrawal_refund",
                        WalletLedgerEntry.reference_id == str(wd_id),
                    )
                )
            ).scalars().all()

            if "approved" in results:
                assert len(outbox_rows) == 1, "Approved withdrawal must have outbox row"
                assert len(refund_rows) == 0, "Approved withdrawal must NOT have refund row (no double spend!)"
            else:
                assert len(outbox_rows) == 0, "Cancelled withdrawal must NOT have outbox row"
                assert len(refund_rows) == 1, "Cancelled withdrawal must have refund row"
    finally:
        # Clean up outbox row so subsequent test suites (e.g. test_withdrawals.py)
        # that assert un-scoped count `where(topic == 'withdrawal') == 0` do not fail.
        from app.services.keys import tx_idempotency_key
        cleanup_outbox_key = tx_idempotency_key("withdrawal", str(wd_id))
        async with sm() as s:
            await s.execute(
                delete(TransactionOutbox).where(
                    TransactionOutbox.topic == "withdrawal",
                    TransactionOutbox.idempotency_key == cleanup_outbox_key,
                )
            )
            await s.commit()


async def test_ai_free_tier_concurrent_requests_cannot_bypass_quota(engine, monkeypatch):
    """When a user has a limited free tier (e.g. 2 free requests) and 0 ORT balance:
    Sending 5 concurrent requests must only allow 2 free slots; the remaining 3 must raise PaymentRequiredError.
    """
    monkeypatch.setattr(settings, "ai_free_requests", 2)
    user_id = await _seed_user(engine, f"ai_race_{uuid.uuid4().hex[:6]}@ex.com", "student")

    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def do_charge():
        async with sm() as s:
            user = await s.get(User, user_id)
            assert user is not None
            try:
                job_ref = uuid.uuid4()
                await AiUsageService(s).charge_job(user=user, job_id=job_ref)
                await s.commit()
                return "ok"
            except PaymentRequiredError:
                await s.rollback()
                return "payment_required"

    # Fire 5 concurrent requests
    outcomes = await asyncio.gather(*(do_charge() for _ in range(5)))

    ok_count = outcomes.count("ok")
    payment_required_count = outcomes.count("payment_required")

    assert ok_count == 2, f"Expected exactly 2 free requests granted, got {ok_count} ({outcomes})"
    assert payment_required_count == 3, f"Expected 3 rejected with 402, got {payment_required_count}"


async def test_counselor_consultation_slot_double_booking_rejected(client):
    """Booking a consultation with the same counselor at the same slot rejects with ConflictError."""
    await register_actor(client, "student1_bk@ex.com", "student")
    slot = (datetime.now(UTC) + timedelta(days=5)).replace(minute=0, second=0, microsecond=0).isoformat()

    # Student 1 books slot
    r1 = await client.post(
        "/api/v1/career/consultations",
        json={
            "counselor": "Bu Ratna Wijaya",
            "topic": "Jurusan Teknik",
            "scheduled_at": slot,
        },
    )
    assert r1.status_code == 200, r1.text
    c1_id = r1.json()["id"]

    # Student 2 tries to book the EXACT SAME counselor and slot -> must get ConflictError (409)
    await register_actor(client, "student2_bk@ex.com", "student")
    r2 = await client.post(
        "/api/v1/career/consultations",
        json={
            "counselor": "Bu Ratna Wijaya",
            "topic": "Jurusan Kedokteran",
            "scheduled_at": slot,
        },
    )
    assert r2.status_code == 409, r2.text
    err_body = r2.json().get("error", {})
    err_msg = (err_body.get("message") or "").lower()
    assert "sudah terisi" in err_msg or "conflict" in err_body.get("code", "").lower()

    # But Student 2 CAN book a DIFFERENT slot for the same counselor
    diff_slot = (datetime.now(UTC) + timedelta(days=6)).replace(minute=0, second=0, microsecond=0).isoformat()
    r3 = await client.post(
        "/api/v1/career/consultations",
        json={
            "counselor": "Bu Ratna Wijaya",
            "topic": "Jurusan Kedokteran",
            "scheduled_at": diff_slot,
        },
    )
    assert r3.status_code == 200, r3.text

    # If Student 1 cancels their consultation, the slot becomes available again
    await client.post(
        "/api/v1/auth/login", json={"email": "student1_bk@ex.com", "password": "Password123!"}
    )
    cancel_resp = await client.post(f"/api/v1/career/consultations/{c1_id}/cancel")
    assert cancel_resp.status_code == 200, cancel_resp.text

    # Now Student 2 can book that previously cancelled slot
    await client.post(
        "/api/v1/auth/login", json={"email": "student2_bk@ex.com", "password": "Password123!"}
    )
    r4 = await client.post(
        "/api/v1/career/consultations",
        json={
            "counselor": "Bu Ratna Wijaya",
            "topic": "Jurusan Kedokteran",
            "scheduled_at": slot,
        },
    )
    assert r4.status_code == 200, r4.text


async def test_quest_attempt_concurrent_recording_idempotent(engine):
    """Concurrent record_attempt calls for the same user and quest must not fail with IntegrityError."""
    user_id = await _seed_user(engine, f"quest_race_{uuid.uuid4().hex[:6]}@ex.com", "student")
    teacher_id = await _seed_user(engine, f"tchr_race_{uuid.uuid4().hex[:6]}@ex.com", "teacher")

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        teacher = await s.get(User, teacher_id)
        assert teacher is not None
        quest = await QuestService(s).create(
            owner=teacher,
            title="Quest Race",
            rules=[],
            status="open",
        )
        quest_id = quest.id
        await s.commit()

    async def do_record():
        async with sm() as s:
            user = await s.get(User, user_id)
            assert user is not None
            attempt = await QuestService(s).record_attempt(
                quest_id=quest_id,
                user=user,
                exam_attempt_id=None,
            )
            await s.commit()
            return str(attempt.id)

    # 3 concurrent calls to record_attempt
    ids = await asyncio.gather(*(do_record() for _ in range(3)))
    # All 3 returned without raising IntegrityError, and reference the same attempt
    assert len(set(ids)) == 1


async def test_exam_concurrent_submit_serialized(engine):
    """Submitting an attempt concurrently from multiple clients must serialize safely and remain submitted."""
    teacher_id = await _seed_user(engine, f"tchr_exam_{uuid.uuid4().hex[:6]}@ex.com", "teacher")
    student_id = await _seed_user(engine, f"std_exam_{uuid.uuid4().hex[:6]}@ex.com", "student")

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        teacher = await s.get(User, teacher_id)
        student = await s.get(User, student_id)
        assert teacher is not None and student is not None

        exam = Exam(
            owner_id=teacher.id,
            title="Concurrency Exam",
            is_active=True,
            status="published",
            duration_minutes=30,
        )
        s.add(exam)
        await s.flush()

        attempt = ExamAttempt(
            exam_id=exam.id,
            user_id=student.id,
            attempt_number=1,
            status="in_progress",
            started_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        s.add(attempt)
        await s.commit()
        attempt_id = attempt.id

    async def do_submit():
        async with sm() as s:
            std = await s.get(User, student_id)
            assert std is not None
            res = await ExamService(s).submit_attempt(attempt_id, std)
            await s.commit()
            return res.status

    statuses = await asyncio.gather(*(do_submit() for _ in range(3)))
    assert all(status == "submitted" for status in statuses)
