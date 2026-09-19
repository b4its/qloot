"""Correlation id middleware: attaches a request id to every request + logs."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core import metrics
from app.core.logging import get_logger

log = get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            metrics.incr("http_requests_total", status="500", method=request.method)
            log.exception("request_failed", duration_ms=duration_ms)
            raise
        duration_s = time.perf_counter() - start
        duration_ms = round(duration_s * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        metrics.incr("http_requests_total", status=str(response.status_code), method=request.method)
        metrics.observe("http_request_duration_seconds", duration_s, method=request.method)
        log.info("request", status=response.status_code, duration_ms=duration_ms)
        return response
