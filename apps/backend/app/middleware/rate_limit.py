"""Redis-backed fixed-window rate limiting.

Used as a FastAPI dependency on sensitive/expensive routes (auth, AI). Keyed by
client IP + a logical bucket name, so limits are per-route-family and survive
multiple workers. Falls back to an in-process counter when Redis is unavailable
so a Redis outage degrades throttling instead of returning 500s.

The limiter is a no-op when ``settings.app_env == "test"`` (the suite fires many
requests per endpoint); the dedicated rate-limit test enables it explicitly.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitedError
from app.core.logging import get_logger

log = get_logger("rate_limit")

# In-process fallback: bucket key -> (window_start_epoch, count).
_local: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))


def _client_ip(request: Request) -> str:
    # Honor the first hop of X-Forwarded-For when behind a proxy, else the peer.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _redis():
    from app.services.realtime import event_bus

    return event_bus._redis  # noqa: SLF001 - shared connection pool


async def _check_redis(key: str, limit: int, window: int) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds) using Redis INCR/EXPIRE."""
    redis = await _redis()
    if redis is None:
        return True, 0
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window)
        if count > limit:
            ttl = await redis.ttl(key)
            return False, max(int(ttl), 1)
        return True, 0
    except Exception as exc:  # noqa: BLE001
        log.warning("rate_limit_redis_error", error=str(exc))
        return True, 0


def _check_local(key: str, limit: int, window: int) -> tuple[bool, int]:
    now = time.monotonic()
    start, count = _local[key]
    if now - start >= window:
        start, count = now, 0
    count += 1
    _local[key] = (start, count)
    if count > limit:
        return False, max(int(window - (now - start)), 1)
    return True, 0


async def enforce(request: Request, bucket: str, limit: int, window: int) -> None:
    """Raise ``RateLimitedError`` (429 + Retry-After) when the bucket is over."""
    if not settings.rate_limit_enabled or settings.app_env == "test":
        return
    key = f"rl:{bucket}:{_client_ip(request)}"
    allowed, retry_after = await _check_redis(key, limit, window)
    if allowed:
        # Redis path may have been unavailable; apply the local fallback too so
        # a Redis outage still throttles per-process.
        redis = await _redis()
        if redis is None:
            allowed, retry_after = _check_local(key, limit, window)
    if not allowed:
        from app.core import metrics

        metrics.incr("rate_limited_total", bucket=bucket)
        raise RateLimitedError(
            "Too many requests. Please slow down and try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit(bucket: str, limit: int | None = None, window: int | None = None):
    """Dependency factory.

    When ``limit``/``window`` are omitted they are resolved from ``settings`` at
    request time (so tests and operators can tune them without re-importing).
    """

    def _resolve() -> tuple[int, int]:
        defaults = {
            "login": settings.rate_limit_login,
            "register": settings.rate_limit_register,
            "password_reset": settings.rate_limit_password_reset,
            "ai": settings.rate_limit_ai,
        }
        lim = limit if limit is not None else defaults.get(bucket, settings.rate_limit_ai)
        win = window if window is not None else settings.rate_limit_window_seconds
        return lim, win

    async def _dep(request: Request) -> None:
        lim, win = _resolve()
        await enforce(request, bucket, lim, win)

    return _dep
