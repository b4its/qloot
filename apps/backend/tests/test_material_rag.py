"""Material RAG: chunk index and retrieval for summary/Q&A (C41)."""

from __future__ import annotations

import pytest

from tests.helpers import register_actor
from tests.pdf_util import make_pdf

pytestmark = pytest.mark.integration


async def _upload(client, text: str) -> str:
    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("m.pdf", make_pdf(text), "application/pdf")},
        data={"title": "Materi"},
    )
    assert up.status_code == 201, up.text
    return up.json()["id"]


async def test_chunks_indexed_on_upload(client, engine):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.learning import MaterialChunk

    await register_actor(client, "rag_t@ex.com", "teacher")
    # Long enough to span multiple chunks.
    body = " ".join(f"Paragraf nomor {i} membahas topik tertentu." for i in range(200))
    material_id = await _upload(client, body)

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        count = (
            await s.execute(
                select(func.count())
                .select_from(MaterialChunk)
                .where(MaterialChunk.material_id == __import__("uuid").UUID(material_id))
            )
        ).scalar_one()
        # Embeddings were stored on the mock provider.
        first = (
            await s.execute(
                select(MaterialChunk)
                .where(MaterialChunk.material_id == __import__("uuid").UUID(material_id))
                .order_by(MaterialChunk.position)
                .limit(1)
            )
        ).scalar_one()
    assert count > 1, "a long document must produce multiple chunks"
    assert first.embedding is not None


async def test_rag_answers_from_end_of_long_document(client):
    """A fact that only appears near the END of a >20k-char document must be
    retrievable (proving RAG, not first-20k-char truncation)."""
    await register_actor(client, "rag2_t@ex.com", "teacher")
    # ~40k chars of filler, then a unique fact at the very end.
    filler = " ".join(
        "Informasi latar belakang tentang berbagai konsep umum tanpa fakta khusus." for _ in range(500)
    )
    fact = "Ibu kota negara Nusantara adalah Kota Cahaya."
    material_id = await _upload(client, filler + "\n" + fact)

    r = await client.post(
        f"/api/v1/materials/{material_id}/ask",
        json={"question": "Di mana ibu kota negara Nusantara?"},
    )
    assert r.status_code == 200, r.text
    answer = r.json()["answer"]
    assert "Kota Cahaya" in answer, answer


async def test_ask_and_summary_reject_non_member(client):
    """RBAC-negative (C41/C42): a user who neither owns the material nor is
    enrolled in its course must get 403 from /ask and /summary."""
    await register_actor(client, "rag_owner@ex.com", "teacher")
    material_id = await _upload(client, "Teks materi rahasia untuk pengujian akses.")
    await client.post("/api/v1/auth/logout")

    await register_actor(client, "rag_outsider@ex.com", "student")
    ask = await client.post(
        f"/api/v1/materials/{material_id}/ask", json={"question": "apa isinya?"}
    )
    assert ask.status_code == 403, ask.text
    summary = await client.get(f"/api/v1/materials/{material_id}/summary")
    assert summary.status_code == 403, summary.text
