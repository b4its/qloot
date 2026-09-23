"""Double-submit CSRF protection.

A non-HttpOnly ``csrf`` cookie is issued on safe requests; unsafe methods must
echo its value in the ``X-CSRF-Token`` header. The comparison is constant-time.

Disabled when ``settings.csrf_enabled`` is false or ``app_env == "test"`` (the
suite posts without cookies); the dedicated CSRF test enables it per-case.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _active() -> bool:
    return settings.csrf_enabled and settings.app_env != "test"


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not _active():
            return await call_next(request)

        cookie = request.cookies.get(settings.csrf_cookie_name)

        if request.method not in _SAFE_METHODS:
            header = request.headers.get(settings.csrf_header_name, "")
            if not cookie or not header or not hmac.compare_digest(cookie, header):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "csrf_failed",
                            "message": "Missing or invalid CSRF token",
                            "detail": None,
                        }
                    },
                )

        response = await call_next(request)
        # Ensure the browser holds a token to echo on the next mutation.
        if not cookie:
            token = secrets.token_urlsafe(32)
            response.set_cookie(
                key=settings.csrf_cookie_name,
                value=token,
                httponly=False,
                secure=settings.session_secure,
                samesite=settings.session_same_site,
                domain=settings.session_cookie_domain,
                path="/",
            )
        return response
