"""QLoot digital assets: per-asset balances, ORX swaps and AI-request spend."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Asset User")


async def _credit_opt(engine, user_id: str, amount: int, ref: str):
    """Credit OPT to a user via the reward engine (test helper)."""
    import uuid as _uuid

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.identity import User
    from app.services.reward_engine import RewardEngine

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        await RewardEngine(s).credit(
            user=await s.get(User, _uuid.UUID(user_id)),
            amount=amount,
            reference_type="reward",
            reference_id=ref,
            reward_key_value=f"rk-{ref}",
            token_id=0,
        )
        await s.commit()


async def test_wallet_assets_lists_three_assets(client):
    await _register(client, "assets_list@ex.com")
    r = await client.get("/api/v1/wallet/assets")
    assert r.status_code == 200, r.text
    body = r.json()
    keys = [a["asset"] for a in body["assets"]]
    assert keys == ["OPT", "QTC", "ORT"]
    for a in body["assets"]:
        assert a["balance"] == 0
        assert a["name"] and a["symbol"] and a["role"]


async def test_swap_requires_opt_balance(client):
    await _register(client, "swap_poor@ex.com")
    r = await client.post("/api/v1/wallet/swap", json={"asset": "ORT", "amount": 10})
    assert r.status_code == 409, r.text  # no OPT to pay with


async def test_swap_opt_to_ort_and_qtc(client, engine):
    user = await _register(client, "swap_rich@ex.com")

    # Credit 100_000 OPT directly via the engine.
    await _credit_opt(engine, user["id"], 100_000, "seed-swap")

    # Buy 10 ORT (50 OPT each = 500 OPT).
    r = await client.post("/api/v1/wallet/swap", json={"asset": "ORT", "amount": 10})
    assert r.status_code == 200, r.text
    balances = {a["asset"]: a["balance"] for a in r.json()["assets"]}
    assert balances["ORT"] == 10
    assert balances["OPT"] == 99_500

    # Buy 2 QTC (1000 OPT each = 2000 OPT).
    r2 = await client.post("/api/v1/wallet/swap", json={"asset": "QTC", "amount": 2})
    assert r2.status_code == 200, r2.text
    balances2 = {a["asset"]: a["balance"] for a in r2.json()["assets"]}
    assert balances2["QTC"] == 2
    assert balances2["OPT"] == 97_500

    # A swap outbox item was enqueued for the worker.
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.wallet import TransactionOutbox

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        topics = (
            (
                await s.execute(
                    select(TransactionOutbox.topic).where(TransactionOutbox.topic == "swap")
                )
            )
            .scalars()
            .all()
        )
    assert len(topics) == 2


async def test_swap_rejects_unsupported_asset(client):
    await _register(client, "swap_bad@ex.com")
    r = await client.post("/api/v1/wallet/swap", json={"asset": "OPT", "amount": 1})
    assert r.status_code == 422, r.text  # schema only allows QTC/ORT


async def test_ai_request_spends_ort(client, engine):
    user = await _register(client, "ai_ort@ex.com")
    await _credit_opt(engine, user["id"], 100_000, "seed-ai")

    # Swap for 5 ORT, then spend 3.
    await client.post("/api/v1/wallet/swap", json={"asset": "ORT", "amount": 5})
    r = await client.post("/api/v1/wallet/ai-requests", json={"requests": 3})
    assert r.status_code == 200, r.text
    balances = {a["asset"]: a["balance"] for a in r.json()["assets"]}
    assert balances["ORT"] == 2

    # Spending more than the balance is rejected.
    over = await client.post("/api/v1/wallet/ai-requests", json={"requests": 10})
    assert over.status_code == 409, over.text


def test_off_chain_rates_match_on_chain_defaults():
    """WEB3-10 parity: the backend-quoted swap rate must equal the contract's
    default rate, so the OPT a user is charged off-chain equals what the proxy
    would burn on-chain."""
    import pathlib
    import re

    from app.core.config import settings

    sol = pathlib.Path(__file__).resolve().parents[3] / "blockchain" / "contracts"
    source = (sol / "OryphemProxy.sol").read_text(encoding="utf-8")
    ort = re.search(r"uint256 public constant ORT_RATE = (\d+);", source)
    qtc = re.search(r"uint256 public constant QTC_RATE = (\d+);", source)
    assert ort is not None and qtc is not None
    assert settings.orx_ort_rate == int(ort.group(1))
    assert settings.orx_qtc_rate == int(qtc.group(1))
    assert settings.orx_rate("ORT") == int(ort.group(1))
    assert settings.orx_rate("QTC") == int(qtc.group(1))

