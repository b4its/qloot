"""Unit tests for Asisten Qlo routing: AI provider preferred, KB as fallback."""

from __future__ import annotations

import uuid

import pytest

from app.ai.provider import AnswerResult
from app.core.config import settings
from app.services.career_service import CareerService

pytestmark = pytest.mark.integration


class _FakeProvider:
    def __init__(self, answer: str = "Jawaban dari model.", boom: bool = False):
        self.answer_text = answer
        self.boom = boom
        self.calls = 0

    async def answer(self, _ctx):
        self.calls += 1
        if self.boom:
            raise RuntimeError("upstream down")
        return AnswerResult(answer=self.answer_text, confidence_bp=8100)


class _User:
    """Minimal stand-in for the fields the KB branch reads."""

    id = uuid.uuid4()


@pytest.mark.asyncio
async def test_assistant_uses_ai_provider_when_configured(session, monkeypatch):
    fake = _FakeProvider(answer="ITB dan UI adalah kampus terbaik.")
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr("app.ai.provider.get_ai_provider", lambda: fake)

    reply = await CareerService(session).assistant_reply(_User(), "kampus terbaik?")

    assert fake.calls == 1
    assert reply["answer"] == "ITB dan UI adalah kampus terbaik."
    assert reply["confidence_bp"] == 8100


@pytest.mark.asyncio
async def test_assistant_falls_back_to_kb_on_ai_failure(session, monkeypatch):
    fake = _FakeProvider(boom=True)
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr("app.ai.provider.get_ai_provider", lambda: fake)

    reply = await CareerService(session).assistant_reply(_User(), "Bedanya SNBP dan SNBT?")

    assert fake.calls == 1
    # KB answer mentions SNBP deterministically.
    assert "SNBP" in reply["answer"]


@pytest.mark.asyncio
async def test_assistant_skips_ai_for_mock_provider(session, monkeypatch):
    fake = _FakeProvider()
    monkeypatch.setattr(settings, "ai_provider", "mock")
    monkeypatch.setattr("app.ai.provider.get_ai_provider", lambda: fake)

    reply = await CareerService(session).assistant_reply(_User(), "siapa kamu?")

    assert fake.calls == 0
    assert "Asisten Qlo" in reply["answer"]
    # The old "Kulo" alias must no longer be advertised.
    assert "Kulo" not in reply["answer"]


@pytest.mark.asyncio
async def test_assistant_kb_uses_configured_name(session, monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "mock")
    monkeypatch.setattr(settings, "assistant_name", "Asisten Qlo")
    reply = await CareerService(session).assistant_reply(_User(), "siapa kamu?")
    assert "Asisten Qlo" in reply["answer"]
    assert "Kulo" not in reply["answer"]
