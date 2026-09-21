"""Unit tests for the OpenAI-compatible AI provider.

Uses httpx.MockTransport so no network is touched. Covers the request shape
(chat/completions + JSON mode), response parsing (incl. code-fenced JSON), and
error handling for transport/shape/schema failures.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.ai.provider import (
    GenerationContext,
    GradeItem,
    GradingContext,
    OpenAICompatProvider,
    QAContext,
    SummaryContext,
)
from app.core.config import settings
from app.core.errors import AIProviderError


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.ai_base_url.rstrip("/"),
        transport=httpx.MockTransport(handler),
        headers={
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        },
    )


def _content(payload: dict) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})


@pytest.mark.asyncio
async def test_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "")
    with pytest.raises(AIProviderError):
        OpenAICompatProvider()


@pytest.mark.asyncio
async def test_answer_uses_chat_completions_and_parses(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return _content({"answer": "ITB dan UI.", "confidence_bp": 8800})

    provider = OpenAICompatProvider(client=_client(handler))
    result = await provider.answer(QAContext(text="konteks", question="kampus?", language="id"))

    assert result.answer == "ITB dan UI."
    assert result.confidence_bp == 8800
    assert seen["url"].endswith("/chat/completions")
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["messages"][0]["role"] == "system"
    await provider.aclose()


@pytest.mark.asyncio
async def test_generate_questions_strips_code_fences(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    fenced = (
        "```json\n"
        + json.dumps({"questions": [{"prompt": "Apa itu X?", "correct_answer": "Y"}]})
        + "\n```"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": fenced}}]})

    provider = OpenAICompatProvider(client=_client(handler))
    result = await provider.generate_questions(GenerationContext(text="materi", count=1))
    assert result.questions[0].prompt == "Apa itu X?"
    await provider.aclose()


@pytest.mark.asyncio
async def test_grade_rejects_wrong_item_count(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        # One item returned, two submitted → must raise.
        return _content({"items": [{"score_bp": 5000}]})

    provider = OpenAICompatProvider(client=_client(handler))
    ctx = GradingContext(
        items=[
            GradeItem(question="q1", correct_answer="a", student_answer="s"),
            GradeItem(question="q2", correct_answer="a", student_answer="s"),
        ]
    )
    with pytest.raises(AIProviderError):
        await provider.grade(ctx)
    await provider.aclose()


@pytest.mark.asyncio
async def test_answer_falls_back_to_plain_text(monkeypatch):
    """Some gateways ignore JSON mode; a prose reply is used as the answer."""
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "Halo, apa kabar?"}}]})

    provider = OpenAICompatProvider(client=_client(handler))
    result = await provider.answer(QAContext(text="t", question="q"))
    assert result.answer == "Halo, apa kabar?"
    assert 0 <= result.confidence_bp <= 10000
    await provider.aclose()


@pytest.mark.asyncio
async def test_transport_error_is_wrapped(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    provider = OpenAICompatProvider(client=_client(handler))
    with pytest.raises(AIProviderError):
        await provider.summarize(SummaryContext(text="materi"))
    await provider.aclose()


@pytest.mark.asyncio
async def test_unexpected_shape_is_wrapped(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    provider = OpenAICompatProvider(client=_client(handler))
    with pytest.raises(AIProviderError):
        await provider.answer(QAContext(text="t", question="q"))
    await provider.aclose()


@pytest.mark.asyncio
async def test_tolerates_trailing_sse_sentinel(monkeypatch):
    """Some gateways append ``data: [DONE]`` to non-streaming bodies.

    A naive ``resp.json()`` would fail with "Extra data"; the provider must
    decode the leading JSON object and ignore the trailing sentinel.
    """
    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    payload = json.dumps({"answer": "OK", "confidence_bp": 9000})
    body = json.dumps({"choices": [{"message": {"content": payload}}]}) + "data: [DONE]"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": "application/json"})

    provider = OpenAICompatProvider(client=_client(handler))
    result = await provider.answer(QAContext(text="t", question="q"))
    assert result.answer == "OK"
    assert result.confidence_bp == 9000
    await provider.aclose()


@pytest.mark.asyncio
async def test_summarize_falls_back_to_prose(monkeypatch):
    """A model that ignores JSON mode must still yield a usable summary."""
    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    prose = (
        "Fotosintesis mengubah cahaya matahari menjadi energi.\n\n"
        "**Poin utama:**\n"
        "1. Tumbuhan menyerap cahaya.\n"
        "2. Oksigen dilepaskan.\n"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": prose}}]})

    provider = OpenAICompatProvider(client=_client(handler))
    result = await provider.summarize(SummaryContext(text="materi"))
    assert result.summary.startswith("Fotosintesis mengubah cahaya matahari")
    assert "Poin utama" not in result.summary
    assert result.key_points == ["Tumbuhan menyerap cahaya.", "Oksigen dilepaskan."]
    await provider.aclose()
