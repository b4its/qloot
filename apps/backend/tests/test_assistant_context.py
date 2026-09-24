"""Assistant personalisation tests (CARE-02).

The assistant must ground its answers in the student's own data (grades,
personality, recommendations) when that data exists, and behave exactly as
before when the profile is empty. Both the AI path and the offline KB
fallback are covered.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Assistant User")


async def _seed_profile(client):
    for subject, grade in [("Matematika", 88), ("Fisika", 94), ("Kimia", 61)]:
        r = await client.post("/api/v1/career/grades", json={"subject": subject, "grade": grade})
        assert r.status_code == 200, r.text
    p = await client.post(
        "/api/v1/career/personality", json={"answers": [4, 5, 3, 4, 5, 2, 4, 5, 3, 4]}
    )
    assert p.status_code == 200, p.text
    g = await client.post("/api/v1/career/recommendations/generate")
    assert g.status_code == 200, g.text


async def test_kb_fallback_personalises_with_profile(client):
    """With grades + personality, a self-referential question answers using the
    student's own data rather than the generic menu."""
    await _register(client, "assist_kb@ex.com")
    await _seed_profile(client)

    resp = await client.post("/api/v1/career/assistant", json={"message": "Bagaimana nilai saya?"})
    assert resp.status_code == 200, resp.text
    answer = resp.json()["answer"]
    assert "profilmu" in answer.lower()
    # A concrete number from the seeded grades must appear.
    assert "94" in answer or "Matematika" in answer or "Fisika" in answer


async def test_kb_fallback_unchanged_without_profile(client):
    """With no data, the assistant gives the original generic answer."""
    await _register(client, "assist_empty@ex.com")
    resp = await client.post("/api/v1/career/assistant", json={"message": "Bagaimana nilai saya?"})
    assert resp.status_code == 200, resp.text
    answer = resp.json()["answer"]
    assert "ringkasan profilmu" not in answer.lower()


async def test_student_profile_context_is_empty_without_data(client):
    await _register(client, "assist_ctx_empty@ex.com")
    sm = client._sm  # type: ignore[attr-defined]
    from sqlalchemy import select

    from app.models.identity import User
    from app.services.career_service import CareerService

    async with sm() as s:
        user = (await s.execute(select(User).where(User.email == "assist_ctx_empty@ex.com"))).scalar_one()
        context = await CareerService(s).student_profile_context(user)
    assert context == ""


async def test_student_profile_context_contains_real_data(client):
    await _register(client, "assist_ctx_data@ex.com")
    await _seed_profile(client)
    sm = client._sm  # type: ignore[attr-defined]
    from sqlalchemy import select

    from app.models.identity import User
    from app.services.career_service import CareerService

    async with sm() as s:
        user = (await s.execute(select(User).where(User.email == "assist_ctx_data@ex.com"))).scalar_one()
        context = await CareerService(s).student_profile_context(user)
    assert "Rata-rata nilai" in context
    assert "Mata pelajaran kuat" in context
    assert "Fisika" in context
    assert "Trait dominan" in context
    assert "Jurusan rekomendasi" in context


async def test_ai_context_includes_the_student_profile(client, monkeypatch):
    """The AI path must inject the profile into QAContext.text."""
    await _register(client, "assist_ai@ex.com")
    await _seed_profile(client)

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
    # career_service imports get_ai_provider lazily inside the method, so patch
    # the source module it imports from.

    sm = client._sm  # type: ignore[attr-defined]
    from sqlalchemy import select

    from app.models.identity import User
    from app.services.career_service import CareerService

    async with sm() as s:
        user = (await s.execute(select(User).where(User.email == "assist_ai@ex.com"))).scalar_one()
        reply = await CareerService(s).assistant_reply(user, "apa jurusan terbaik untukku?")
    assert reply["answer"] == "ok"
    assert "Data siswa ini" in captured["text"]
    assert "Mata pelajaran kuat" in captured["text"]
