"""Prometheus metrics endpoint."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Response, status

from app.core import metrics
from app.core.config import settings

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics_endpoint(
    authorization: str | None = Header(default=None),
) -> Response:
    # When METRICS_TOKEN is configured, require a matching bearer token so
    # process metrics are not exposed on a publicly routable API. Empty token
    # keeps the historical open behaviour (backwards-compatible).
    expected = settings.metrics_token
    if expected:
        presented = ""
        if authorization and authorization.lower().startswith("bearer "):
            presented = authorization[7:].strip()
        if not hmac.compare_digest(presented, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return Response(content=metrics.render(), media_type="text/plain; version=0.0.4")
