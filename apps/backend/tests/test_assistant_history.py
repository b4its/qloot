"""Assistant conversation history tests (CARE-01).

The assistant was stateless: follow-up questions had no context. These tests
prove turns are persisted, can be listed/loaded/deleted, and that recent turns
are replayed to the provider (bounded).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="History User")


async def test_first_message_creates_a_conversation(client):
    await _register(client, "hist_first@ex.com")
    r = await client.post("/api/v1/career/assistant", json={"message": "Apa itu SNBP?"})
    assert r.status_code == 200, r.text
    conv_id = r.json()["conversation_id"]
    assert conv_id

    detail = await client.get(f"/api/v1/career/assistant/conversations/{conv_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "assistant"]


async def test_followup_replays_previous_turns_to_the_provider(client, monkeypatch):
    """A follow-up must be answered with the previous turns in the AI context."""
    await _register(client, "hist_follow@ex.com")
    first = await client.post("/api/v1/career/assistant", json={"message": "Ceritakan SNBP"})
    conv_id = first.json()["conversation_id"]

    captured: dict = {}

    class _FakeProvider:
        async def answer(self, ctx):
            captured["text"] = ctx.text
            from app.ai.provider import AnswerResult

            return AnswerResult(answer="ok", confidence_bp=8000)

    import app.ai.provider as provider_mod
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "ai_provider", "openai")
    monkeypatch.setattr(provider_mod, "get_ai_provider", lambda: _FakeProvider())

    second = await client.post(
        "/api/v1/career/assistant",
        json={"message": "dan biayanya?", "conversation_id": conv_id},
    )
    assert second.status_code == 200, second.text
    assert second.json()["conversation_id"] == conv_id
    assert "Percakapan sebelumnya" in captured["text"]
    assert "Ceritakan SNBP" in captured["text"]


async def test_conversation_can_be_listed_and_deleted(client):
    await _register(client, "hist_list@ex.com")
    r1 = await client.post("/api/v1/career/assistant", json={"message": "Halo"})
    r2 = await client.post("/api/v1/career/assistant", json={"message": "Apa itu UTBK?"})
    conv_ids = {r1.json()["conversation_id"], r2.json()["conversation_id"]}

    listing = await client.get("/api/v1/career/assistant/conversations")
    assert listing.status_code == 200
    listed = {c["id"] for c in listing.json()}
    assert conv_ids <= listed

    target = r1.json()["conversation_id"]
    deleted = await client.delete(f"/api/v1/career/assistant/conversations/{target}")
    assert deleted.status_code == 200, deleted.text
    gone = await client.get(f"/api/v1/career/assistant/conversations/{target}")
    assert gone.status_code == 404


async def test_conversation_history_is_owner_scoped(client):
    await _register(client, "hist_owner_a@ex.com")
    r = await client.post("/api/v1/career/assistant", json={"message": "rahasia"})
    conv_id = r.json()["conversation_id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "hist_owner_b@ex.com")
    other = await client.get(f"/api/v1/career/assistant/conversations/{conv_id}")
    assert other.status_code == 404
    other_del = await client.delete(f"/api/v1/career/assistant/conversations/{conv_id}")
    assert other_del.status_code == 404


async def test_recent_turns_are_bounded(client):
    """Replay is capped so the provider context cannot grow unbounded."""
    await _register(client, "hist_bound@ex.com")
    r = await client.post("/api/v1/career/assistant", json={"message": "mulai"})
    conv_id = r.json()["conversation_id"]
    for i in range(10):
        await client.post(
            "/api/v1/career/assistant",
            json={"message": f"pesan {i}", "conversation_id": conv_id},
        )

    sm = client._sm  # type: ignore[attr-defined]
    import uuid as _uuid

    from app.services.career_service import CareerService

    async with sm() as s:
        turns = await CareerService(s)._recent_turns(_uuid.UUID(conv_id), limit=6)
    assert len(turns) == 6
