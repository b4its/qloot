"""Assistant streaming + accessibility tests (CARE-04, UIX-02)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Stream User")


async def test_provider_default_stream_matches_answer():
    """The default answer_stream must yield the same text as answer()."""
    from app.ai.provider import MockProvider, QAContext

    provider = MockProvider()
    ctx = QAContext(text="SNBP adalah jalur masuk tanpa tes.", question="apa itu snbp?")
    result = await provider.answer(ctx)
    chunks = [c async for c in provider.answer_stream(ctx)]
    assert "".join(chunks) == result.answer


async def test_assistant_stream_returns_sse_frames(client):
    await _register(client, "stream_user@ex.com")
    async with client.stream(
        "POST",
        "/api/v1/career/assistant/stream",
        json={"message": "Apa itu SNBP?"},
        headers={"Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200, await resp.aread()
        assert "text/event-stream" in resp.headers["content-type"]
        body = ""
        async for line in resp.aiter_lines():
            body += line + "\n"

    assert "data:" in body
    assert "event: done" in body
    # The streamed answer mentions SNBP (deterministic KB answer).
    assert "SNBP" in body


async def test_assistant_json_fallback_still_works(client):
    """The non-streaming JSON endpoint remains the fallback."""
    await _register(client, "stream_json@ex.com")
    r = await client.post("/api/v1/career/assistant", json={"message": "Apa itu SNBT?"})
    assert r.status_code == 200, r.text
    assert "SNBT" in r.json()["answer"]


async def test_assistant_stream_failure_refunds_ort_idempotently(
    client, engine, monkeypatch
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.config import settings
    from app.models.wallet import AiUsageCharge
    from app.services.ai_usage_service import AiUsageService
    from app.services.career_service import CareerService
    from app.services.reward_engine import RewardEngine

    monkeypatch.setattr(settings, "ai_free_requests", 0)
    user = await _register(client, "stream_refund@ex.com")
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session, session.begin():
        await RewardEngine(session).credit_asset(
            user_id=user["id"], asset="ORT", amount=1
        )

    async def failed_stream(*args, **kwargs):
        raise RuntimeError("provider unavailable")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(CareerService, "assistant_reply_stream", failed_stream)
    async with client.stream(
        "POST",
        "/api/v1/career/assistant/stream",
        json={"message": "Apa itu SNBP?"},
    ) as resp:
        body = (await resp.aread()).decode()

    assert resp.status_code == 200
    assert "event: error" in body
    # The client must get a generic message, not provider internals.
    assert "provider unavailable" not in body
    assert "Streaming gagal" in body

    async with sm() as session:
        charge = (
            await session.execute(
                select(AiUsageCharge).where(AiUsageCharge.user_id == user["id"])
            )
        ).scalar_one()
        assert charge.charged is True
        assert charge.refunded is True
        assert await RewardEngine(session).asset_balance(user["id"], "ORT") == 1

        async with session.begin_nested():
            await AiUsageService(session).refund_job(
                user_id=user["id"], job_id=charge.job_id
            )
        assert await RewardEngine(session).asset_balance(user["id"], "ORT") == 1


async def test_assistant_provider_stream_failure_refunds_ort(
    client, engine, monkeypatch
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.ai import provider as provider_module
    from app.core.config import settings
    from app.models.wallet import AiUsageCharge
    from app.services.reward_engine import RewardEngine

    class FailedProvider:
        async def answer_stream(self, ctx):
            raise RuntimeError("provider unavailable")
            yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "ai_free_requests", 0)
    monkeypatch.setattr(provider_module, "get_ai_provider", lambda: FailedProvider())
    user = await _register(client, "provider_stream_refund@ex.com")
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session, session.begin():
        await RewardEngine(session).credit_asset(
            user_id=user["id"], asset="ORT", amount=1
        )

    async with client.stream(
        "POST",
        "/api/v1/career/assistant/stream",
        json={"message": "Apa itu SNBP?"},
    ) as resp:
        body = (await resp.aread()).decode()

    assert resp.status_code == 200
    assert "SNBP" in body
    assert "event: done" in body
    async with sm() as session:
        charge = (
            await session.execute(
                select(AiUsageCharge).where(AiUsageCharge.user_id == user["id"])
            )
        ).scalar_one()
        assert charge.refunded is True
        assert await RewardEngine(session).asset_balance(user["id"], "ORT") == 1
