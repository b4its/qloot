"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_sessionmaker

router = APIRouter()


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


async def _check_database() -> str:
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001 - report, never raise from readiness
        return f"error: {type(exc).__name__}"


async def _check_redis() -> str:
    """Ping Redis (realtime pub/sub + rate-limit backend).

    A failure here must not raise — readiness reports it as a degraded
    dependency rather than crashing the probe.
    """
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.ping()
        finally:
            await client.aclose()  # type: ignore[attr-defined]
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}"


def _check_storage() -> str:
    """Probe the object store (MinIO) or local filesystem."""
    from app.services.storage import storage

    try:
        return "ok" if storage.ping() else "error: unreachable"
    except Exception as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}"


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    checks: dict[str, str] = {
        "database": await _check_database(),
    }
    if settings.readiness_check_redis:
        checks["redis"] = await _check_redis()
    if settings.readiness_check_storage:
        checks["storage"] = _check_storage()

    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": checks}
