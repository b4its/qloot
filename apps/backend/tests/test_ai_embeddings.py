"""Provider embed() capability (C40)."""

from __future__ import annotations

import pytest

from app.ai.provider import MockProvider, cosine_similarity
from app.core.config import settings


async def test_mock_embedding_is_deterministic_and_sized():
    provider = MockProvider()
    texts = ["fotosintesis mengubah cahaya", "respirasi menguraikan glukosa"]
    first = await provider.embed(texts)
    second = await provider.embed(texts)
    assert first == second, "embeddings must be stable across calls"
    assert len(first) == len(texts)
    assert all(len(v) == settings.ai_embedding_dim for v in first)


async def test_mock_embedding_similarity_signal():
    provider = MockProvider()
    a = "Fotosintesis mengubah cahaya matahari menjadi energi kimia."
    b = "Proses fotosintesis mengubah cahaya matahari menjadi energi kimia."
    c = "Pajak pertambahan nilai dikenakan atas penyerahan barang."
    va, vb, vc = await provider.embed([a, b, c])
    # Near-duplicate sentences are more similar than an unrelated one.
    assert cosine_similarity(va, vb) > cosine_similarity(va, vc)


async def test_mock_embedding_stable_across_processes():
    """Same input -> same vector even across separate provider instances."""
    t = "energi kinetik benda bermassa"
    v1 = (await MockProvider().embed([t]))[0]
    v2 = (await MockProvider().embed([t]))[0]
    assert v1 == v2


async def test_empty_text_is_zero_vector():
    provider = MockProvider()
    (v,) = await provider.embed([""])
    assert len(v) == settings.ai_embedding_dim
    assert all(x == 0.0 for x in v)


async def test_real_provider_fail_fast_without_embedding_model(monkeypatch):
    from app.ai.provider import OpenAICompatProvider
    from app.core.errors import AIProviderError

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_embedding_model", "")
    p = OpenAICompatProvider()
    with pytest.raises(AIProviderError):
        await p.embed(["x"])
    await p.aclose()
