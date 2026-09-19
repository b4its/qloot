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


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    checks: dict[str, str] = {}

    # Database
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"

    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": checks}
