"""AI usage metering — charge/refund idempotency and atomicity (C09 regression).

These are integration tests (they need the test PostgreSQL) because the bug they
guard is about transaction/savepoint boundaries.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.models.identity import Role, User, UserRole
from app.models.wallet import AiUsageCharge
from app.services.ai_usage_service import AiUsageService
from app.services.reward_engine import RewardEngine

pytestmark = pytest.mark.integration


@pytest.fixture
def no_free_tier(monkeypatch):
    monkeypatch.setattr(settings, "ai_free_requests", 0)
    yield


async def _mk_student(engine) -> uuid.UUID:
    from app.core.security import hash_password

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        from sqlalchemy import select

        role = (await s.execute(select(Role).where(Role.name == "student"))).scalar_one()
        u = User(
            email=f"aiu_{uuid.uuid4().hex[:8]}@ex.com",
            full_name="AIU",
            password_hash=hash_password("Password123!"),
            chain_user_ref="0x" + uuid.uuid4().hex + uuid.uuid4().hex,
        )
        s.add(u)
        await s.flush()
        s.add(UserRole(user_id=u.id, role_id=role.id))
        await s.commit()
        return u.id


async def test_duplicate_charge_race_does_not_leak_ort(engine, no_free_tier):
    """If a concurrent charge wins the unique(job_id) race, the loser must not
    keep its ORT debit — the debit and the charge row share one savepoint."""
    sm = async_sessionmaker(engine, expire_on_commit=False)
    user_id = await _mk_student(engine)
    job_id = uuid.uuid4()

    async with sm() as s:
        await RewardEngine(s).credit_asset(user_id=user_id, asset="ORT", amount=10)
        await s.commit()

    async with sm() as s:
        user = await s.get(User, user_id)
        svc = AiUsageService(s)
        # Simulate the race: the first existence check misses the row even though
        # another transaction already inserted it for this job.
        original = svc._get_charge
        calls = {"n": 0}

        async def _miss_then_hit(jid):  # noqa: ANN001
            calls["n"] += 1
            if calls["n"] == 1:
                return None
            return await original(jid)

        svc._get_charge = _miss_then_hit  # type: ignore[method-assign]

        # Seed the winning charge row directly (as if it committed first).
        winner = AiUsageCharge(job_id=job_id, user_id=user_id, charged=True)
        s.add(winner)
        await s.flush()

        await svc.charge_job(user=user, job_id=job_id)
        await s.commit()

    async with sm() as s:
        # Exactly one charge row, and the ORT balance is untouched by the loser.
        rows = (
            await s.execute(
                AiUsageCharge.__table__.select().where(AiUsageCharge.job_id == job_id)
            )
        ).all()
        assert len(rows) == 1
        assert await RewardEngine(s).asset_balance(user_id, "ORT") == 10
