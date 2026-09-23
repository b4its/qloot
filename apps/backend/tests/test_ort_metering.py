"""AI usage metering: 1 request = 1 ORT, free-tier, and refund on failure (C09)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from tests.helpers import register_actor
from tests.pdf_util import make_pdf

pytestmark = pytest.mark.integration


@pytest.fixture
def no_free_tier(monkeypatch):
    """Disable the free AI tier so ORT is required for every request."""
    monkeypatch.setattr(settings, "ai_free_requests", 0)
    yield


async def _credit_ort(engine, user_id, amount: int):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.services.reward_engine import RewardEngine as _RE

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        await _RE(s).credit_asset(user_id=user_id, asset="ORT", amount=amount)
        await s.commit()


async def _upload_material(client) -> str:
    pdf = make_pdf(
        "Pembelajaran mesin adalah cabang kecerdasan buatan yang mempelajari pola data."
    )
    resp = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("materi.pdf", pdf, "application/pdf")},
        data={"title": "Materi AI"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _ort_balance(client) -> int:
    r = await client.get("/api/v1/wallet/assets")
    assert r.status_code == 200, r.text
    return next(a["balance"] for a in r.json()["assets"] if a["asset"] == "ORT")


async def test_generation_requires_and_spends_ort(client, engine, no_free_tier):
    await register_actor(client, "ort_t@ex.com", "teacher")
    me = (await client.get("/api/v1/auth/me")).json()["id"]
    material_id = await _upload_material(client)

    # No ORT and no free tier (Redis down in tests) -> 402, no job persisted.
    blocked = await client.post(
        f"/api/v1/materials/{material_id}/generate-questions",
        json={"count": 2, "language": "id"},
    )
    assert blocked.status_code == 402, blocked.text

    # Fund 1 ORT -> the generation is accepted and debits exactly one.
    await _credit_ort(engine, me, 1)
    assert await _ort_balance(client) == 1
    ok = await client.post(
        f"/api/v1/materials/{material_id}/generate-questions",
        json={"count": 2, "language": "id"},
    )
    assert ok.status_code == 200, ok.text
    assert await _ort_balance(client) == 0


async def test_ort_refunded_on_generation_failure(client, engine, no_free_tier):
    await register_actor(client, "ort_refund_t@ex.com", "teacher")
    me = (await client.get("/api/v1/auth/me")).json()["id"]
    material_id = await _upload_material(client)
    await _credit_ort(engine, me, 1)

    opened = await client.post(
        f"/api/v1/materials/{material_id}/generate-questions",
        json={"count": 2, "language": "id"},
    )
    assert opened.status_code == 200, opened.text
    job_id = opened.json()["job_id"]
    assert await _ort_balance(client) == 0

    # Run the worker generation path with a provider that always fails.
    import app.services.material_service as mat
    from app.core.errors import AIProviderError

    class _Boom:
        async def generate_questions(self, ctx):  # noqa: ANN001
            raise AIProviderError("provider down")

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.exam import GradingJob
    from app.workers.main import _run_generation

    sm = async_sessionmaker(engine, expire_on_commit=False)
    orig = mat.get_ai_provider
    mat.get_ai_provider = lambda: _Boom()  # type: ignore[assignment]
    try:
        async with sm() as s:
            import uuid as _uuid

            job = await s.get(GradingJob, _uuid.UUID(job_id))
            assert job is not None
            job.max_attempts = 1
            job.attempts = 1
            await s.commit()
            await _run_generation(s, job.id)
            await s.commit()
    finally:
        mat.get_ai_provider = orig  # type: ignore[assignment]

    assert await _ort_balance(client) == 1


async def test_first_requests_are_free(client, monkeypatch):
    """With the free tier on, the first N AI requests cost no ORT."""
    monkeypatch.setattr(settings, "ai_free_requests", 2)
    await register_actor(client, "ort_free_t@ex.com", "teacher")
    material_id = await _upload_material(client)

    for _ in range(2):
        r = await client.post(
            f"/api/v1/materials/{material_id}/generate-questions",
            json={"count": 2, "language": "id"},
        )
        assert r.status_code == 200, r.text
    # Free tier exhausted with no ORT spent -> next request is 402.
    assert await _ort_balance(client) == 0
    blocked = await client.post(
        f"/api/v1/materials/{material_id}/generate-questions",
        json={"count": 2, "language": "id"},
    )
    assert blocked.status_code == 402, blocked.text
