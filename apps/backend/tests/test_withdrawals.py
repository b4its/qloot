"""Withdrawal approval state machine, limits and fees (C12)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.errors import ConflictError
from app.models.identity import User
from app.models.wallet import TransactionOutbox
from app.services.reward_engine import RewardEngine
from app.services.withdrawal_service import WithdrawalService
from tests.helpers import register_actor

pytestmark = pytest.mark.integration

DEST = "0x" + "1" * 40


async def _credit_opt(engine, user_id: str, amount: int):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        await RewardEngine(s).credit(
            user=await s.get(User, uuid.UUID(user_id)),
            amount=amount,
            reference_type="reward",
            reference_id=f"wd-seed-{user_id}",
            reward_key_value=f"rk-wd-{user_id}",
            token_id=0,
        )
        await s.commit()


async def _me(client) -> str:
    return (await client.get("/api/v1/auth/me")).json()["id"]


async def _balance(client) -> int:
    return (await client.get("/api/v1/wallet")).json()["available"]


async def test_withdrawal_stays_requested_without_outbox(client, engine):
    await register_actor(client, "wd_req@ex.com", "student")
    me = await _me(client)
    await _credit_opt(engine, me, 500)

    r = await client.post(
        "/api/v1/wallet/withdrawals", json={"amount": 100, "destination_address": DEST}
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "requested"
    assert await _balance(client) == 400

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        rows = (
            await s.execute(
                select(TransactionOutbox).where(TransactionOutbox.topic == "withdrawal")
            )
        ).scalars().all()
    assert rows == []


async def test_withdrawal_limits(client, engine, monkeypatch):
    monkeypatch.setattr(settings, "withdrawal_min_amount", 10)
    monkeypatch.setattr(settings, "withdrawal_max_amount", 1000)
    await register_actor(client, "wd_lim@ex.com", "student")
    me = await _me(client)
    await _credit_opt(engine, me, 5000)

    below = await client.post(
        "/api/v1/wallet/withdrawals",
        json={"amount": 9, "destination_address": DEST},
    )
    assert below.status_code == 422, below.text

    over = await client.post(
        "/api/v1/wallet/withdrawals",
        json={"amount": 1001, "destination_address": DEST},
    )
    assert over.status_code == 422, over.text


async def test_withdrawal_fee_debited_separately(client, engine, monkeypatch):
    monkeypatch.setattr(settings, "withdrawal_fee", 5)
    await register_actor(client, "wd_fee@ex.com", "student")
    me = await _me(client)
    await _credit_opt(engine, me, 200)

    r = await client.post(
        "/api/v1/wallet/withdrawals", json={"amount": 100, "destination_address": DEST}
    )
    assert r.status_code == 201, r.text
    assert r.json()["fee_amount"] == 5
    assert await _balance(client) == 95  # 200 - 100 - 5


async def test_approve_enqueues_outbox_and_cannot_reapprove(client, engine):
    await register_actor(client, "wd_appr_s@ex.com", "student")
    me = await _me(client)
    await _credit_opt(engine, me, 500)
    wd = (
        await client.post(
            "/api/v1/wallet/withdrawals", json={"amount": 100, "destination_address": DEST}
        )
    ).json()

    await register_actor(client, "wd_appr_a@ex.com", "admin")
    admin_id = await _me(client)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        admin = await s.get(User, uuid.UUID(admin_id))
        svc = WithdrawalService(s)
        approved = await svc.approve(admin=admin, withdrawal_id=uuid.UUID(wd["id"]))
        assert approved.status == "approved"
        await s.commit()
        with pytest.raises(ConflictError):
            await svc.approve(admin=admin, withdrawal_id=uuid.UUID(wd["id"]))
        rows = (
            await s.execute(
                select(TransactionOutbox).where(TransactionOutbox.topic == "withdrawal")
            )
        ).scalars().all()
    assert len(rows) == 1


async def test_reject_refunds_the_user(client, engine):
    await register_actor(client, "wd_rej_s@ex.com", "student")
    me = await _me(client)
    await _credit_opt(engine, me, 500)
    wd = (
        await client.post(
            "/api/v1/wallet/withdrawals", json={"amount": 100, "destination_address": DEST}
        )
    ).json()
    assert await _balance(client) == 400

    await register_actor(client, "wd_rej_a@ex.com", "admin")
    admin_id = await _me(client)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        admin = await s.get(User, uuid.UUID(admin_id))
        await WithdrawalService(s).reject(
            admin=admin, withdrawal_id=uuid.UUID(wd["id"]), reason="suspicious"
        )
        await s.commit()

    # Log back in as the student and confirm the refund.
    await client.post("/api/v1/auth/login", json={"email": "wd_rej_s@ex.com", "password": "Password123!"})
    assert await _balance(client) == 500


async def test_admin_review_endpoints_and_user_cancel(client, engine):
    # Student requests, then cancels from the wallet (funds returned).
    await register_actor(client, "wd_admin_s@ex.com", "student")
    me = await _me(client)
    await _credit_opt(engine, me, 500)
    wd = (
        await client.post(
            "/api/v1/wallet/withdrawals", json={"amount": 100, "destination_address": DEST}
        )
    ).json()
    cancel = await client.post(f"/api/v1/wallet/withdrawals/{wd['id']}/cancel")
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"
    assert await _balance(client) == 500

    # A second withdrawal, reviewed by admin via the HTTP endpoints.
    wd2 = (
        await client.post(
            "/api/v1/wallet/withdrawals", json={"amount": 100, "destination_address": DEST}
        )
    ).json()

    await register_actor(client, "wd_admin_a@ex.com", "admin")
    queue = await client.get("/api/v1/admin/withdrawals?status_filter=requested")
    assert queue.status_code == 200, queue.text
    assert any(w["id"] == wd2["id"] for w in queue.json())

    approved = await client.post(f"/api/v1/admin/withdrawals/{wd2['id']}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    # Already-approved cannot be approved again.
    again = await client.post(f"/api/v1/admin/withdrawals/{wd2['id']}/approve")
    assert again.status_code == 409, again.text


async def test_user_cannot_cancel_after_approval(client, engine):
    await register_actor(client, "wd_late_s@ex.com", "student")
    me = await _me(client)
    await _credit_opt(engine, me, 500)
    wd = (
        await client.post(
            "/api/v1/wallet/withdrawals", json={"amount": 100, "destination_address": DEST}
        )
    ).json()

    await register_actor(client, "wd_late_a@ex.com", "admin")
    await client.post(f"/api/v1/admin/withdrawals/{wd['id']}/approve")

    # Log back in as the student: cancel must now be refused.
    await client.post(
        "/api/v1/auth/login",
        json={"email": "wd_late_s@ex.com", "password": "Password123!"},
    )
    late = await client.post(f"/api/v1/wallet/withdrawals/{wd['id']}/cancel")
    assert late.status_code == 409, late.text


async def test_admin_rejects_with_reason(client, engine):
    await register_actor(client, "wd_aj_s@ex.com", "student")
    me = await _me(client)
    await _credit_opt(engine, me, 500)
    wd = (
        await client.post(
            "/api/v1/wallet/withdrawals", json={"amount": 100, "destination_address": DEST}
        )
    ).json()

    await register_actor(client, "wd_aj_a@ex.com", "admin")
    rej = await client.post(
        f"/api/v1/admin/withdrawals/{wd['id']}/reject", json={"reason": "KYC failed"}
    )
    assert rej.status_code == 200, rej.text
    assert rej.json()["status"] == "rejected"

    await client.post(
        "/api/v1/auth/login",
        json={"email": "wd_aj_s@ex.com", "password": "Password123!"},
    )
    assert await _balance(client) == 500
