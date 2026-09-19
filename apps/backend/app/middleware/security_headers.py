"""Security headers middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self' " + " ".join(settings.cors_origins) + "; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("X-XSS-Protection", "0")
        headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        # CSP only matters for HTML; APIs can still send it safely.
        if request.url.path not in ("/docs", "/redoc", "/openapi.json"):
            headers.setdefault("Content-Security-Policy", _CSP)
        if settings.is_production:
            headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response
