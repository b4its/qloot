"""Prometheus metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.core import metrics

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics_endpoint() -> Response:
    return Response(content=metrics.render(), media_type="text/plain; version=0.0.4")
