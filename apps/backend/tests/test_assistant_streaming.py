"""Assistant streaming + accessibility tests (CARE-04, UIX-02)."""

from __future__ import annotations

import pytest

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
