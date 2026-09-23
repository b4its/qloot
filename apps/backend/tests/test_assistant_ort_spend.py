"""Assistant ORT metering: 1 request = 1 ORT with a clear zero-balance message (C10)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from tests.helpers import register_actor

pytestmark = pytest.mark.integration


async def _credit_ort(engine, user_id, amount: int):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.services.reward_engine import RewardEngine

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        await RewardEngine(s).credit_asset(user_id=user_id, asset="ORT", amount=amount)
        await s.commit()


async def _ort_balance(client) -> int:
    r = await client.get("/api/v1/wallet/assets")
    return next(a["balance"] for a in r.json()["assets"] if a["asset"] == "ORT")


async def test_assistant_charges_ort(client, engine, monkeypatch):
    monkeypatch.setattr(settings, "ai_free_requests", 0)
    await register_actor(client, "asst_t@ex.com", "student")
    me = (await client.get("/api/v1/auth/me")).json()["id"]

    # No ORT -> 402 with a clear message.
    blocked = await client.post("/api/v1/career/assistant", json={"message": "Halo"})
    assert blocked.status_code == 402, blocked.text
    assert "ORT" in blocked.json()["error"]["message"]

    # Fund 1 ORT -> the request succeeds and debits one ORT.
    await _credit_ort(engine, me, 1)
    ok = await client.post("/api/v1/career/assistant", json={"message": "Bagaimana cara belajar?"})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["answer"]
    assert body["ort_balance"] == 0
    assert await _ort_balance(client) == 0


async def test_assistant_free_tier_does_not_spend_ort(client, monkeypatch):
    monkeypatch.setattr(settings, "ai_free_requests", 1)
    await register_actor(client, "asst_free@ex.com", "student")

    first = await client.post("/api/v1/career/assistant", json={"message": "Halo"})
    assert first.status_code == 200, first.text
    assert first.json()["free_requests_remaining"] == 0
    assert await _ort_balance(client) == 0

    # Free tier exhausted, no ORT -> blocked.
    second = await client.post("/api/v1/career/assistant", json={"message": "Lagi"})
    assert second.status_code == 402, second.text
