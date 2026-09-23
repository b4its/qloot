"""Ledger reconciliation: drift detection, repair, metric, admin surface (C15)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import metrics
from app.models.identity import User
from app.models.wallet import WalletAccount
from app.services.reward_engine import RewardEngine
from tests.helpers import register_actor

pytestmark = pytest.mark.integration


async def test_reconcile_all_detects_and_repairs_drift(client, engine):
    await register_actor(client, "recon_s@ex.com", "student")
    me = (await client.get("/api/v1/auth/me")).json()["id"]

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        eng = RewardEngine(s)
        user = await s.get(User, uuid.UUID(me))
        await eng.credit(
            user=user,
            amount=100,
            reference_type="reward",
            reference_id="recon-1",
            reward_key_value="rk-recon-1",
            token_id=0,
        )
        await s.commit()

    # Inject drift: cached_balance no longer matches the ledger (should be 100).
    async with sm() as s:
        await s.execute(
            update(WalletAccount)
            .where(WalletAccount.user_id == uuid.UUID(me))
            .values(cached_balance=999)
        )
        await s.commit()

    before = sum(
        v for k, v in metrics._counters.items()  # noqa: SLF001
        if k.startswith("ledger_reconciliation_errors_total")
    )
    async with sm() as s:
        drifted = await RewardEngine(s).reconcile_all(limit=100000)
        await s.commit()
    after = sum(
        v for k, v in metrics._counters.items()  # noqa: SLF001
        if k.startswith("ledger_reconciliation_errors_total")
    )

    matches = [d for d in drifted if d["user_id"] == me]
    assert matches, "our drifted account must be reported"
    row = matches[0]
    assert row["cached"] == 999
    assert row["expected"] == 100
    assert after > before

    # The cached balance was repaired to the ledger value.
    async with sm() as s:
        account = (
            await s.execute(
                WalletAccount.__table__.select().where(WalletAccount.user_id == uuid.UUID(me))
            )
        ).first()
    assert account.cached_balance == 100


async def test_reconcile_reports_no_drift_when_consistent(client, engine):
    await register_actor(client, "recon_ok@ex.com", "student")
    me = (await client.get("/api/v1/auth/me")).json()["id"]

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        eng = RewardEngine(s)
        user = await s.get(User, uuid.UUID(me))
        await eng.credit(
            user=user,
            amount=50,
            reference_type="reward",
            reference_id="recon-ok",
            reward_key_value="rk-recon-ok",
            token_id=0,
        )
        await s.commit()

    async with sm() as s:
        drifted = await RewardEngine(s).reconcile_all(limit=100000)
    assert all(d["user_id"] != me for d in drifted)


async def test_worker_reconcile_once(client, engine):
    from app.workers.reconciler import reconcile_once

    # Should run without error and return an int count.
    n = await reconcile_once()
    assert isinstance(n, int)


async def test_admin_reconcile_endpoint(client, engine):
    await register_actor(client, "recon_a@ex.com", "admin")
    r = await client.post("/api/v1/admin/ledger/reconcile")
    assert r.status_code == 200, r.text
    assert "drifted" in r.json() and "count" in r.json()
