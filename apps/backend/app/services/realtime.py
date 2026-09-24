"""Realtime event bus: Redis pub/sub with an in-process fallback.

Used for live room leaderboards and presence. Degrades gracefully when Redis
is unavailable (single-process dev/test).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis

log = get_logger("realtime")


class EventBus:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._local_subscribers: dict[str, set[asyncio.Queue]] = {}
        # In-process fallback for incr/decr_connection when Redis is
        # unavailable (dev/test single-process). Redis-backed values live
        # under a "presence:" key prefix instead of a local dict.
        self._local_presence: dict[str, int] = {}

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self._redis.ping()
            log.info("realtime_redis_connected")
        except Exception as exc:  # noqa: BLE001
            log.warning("realtime_redis_unavailable", error=str(exc))
            self._redis = None

    async def close(self) -> None:
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.aclose()  # type: ignore[attr-defined]

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        data = json.dumps(message, default=str)
        if self._redis is not None:
            try:
                await self._redis.publish(channel, data)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("realtime_publish_failed", error=str(exc))
        # Local fallback
        for q in list(self._local_subscribers.get(channel, set())):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(message)

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        if self._redis is not None:
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe(channel)
                try:
                    async for msg in pubsub.listen():
                        if msg.get("type") == "message":
                            yield json.loads(msg["data"])
                finally:
                    await pubsub.unsubscribe(channel)
                    await pubsub.aclose()  # type: ignore[attr-defined]
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("realtime_subscribe_failed", error=str(exc))

        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._local_subscribers.setdefault(channel, set()).add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._local_subscribers.get(channel, set()).discard(queue)

    async def incr_connection(self, key: str) -> int:
        """Increment a live-socket counter for ``key`` (e.g. ``room:user``)
        and return the new count. Backed by Redis when available (accurate
        across replicas); falls back to an in-process counter otherwise.
        """
        if self._redis is not None:
            try:
                return int(await self._redis.incr(f"presence:{key}"))
            except Exception as exc:  # noqa: BLE001
                log.warning("realtime_presence_incr_failed", error=str(exc))
        self._local_presence[key] = self._local_presence.get(key, 0) + 1
        return self._local_presence[key]

    async def decr_connection(self, key: str) -> int:
        """Decrement the counter from :meth:`incr_connection`, floored at 0."""
        if self._redis is not None:
            try:
                new = int(await self._redis.decr(f"presence:{key}"))
                if new <= 0:
                    with contextlib.suppress(Exception):
                        await self._redis.delete(f"presence:{key}")
                    return 0
                return new
            except Exception as exc:  # noqa: BLE001
                log.warning("realtime_presence_decr_failed", error=str(exc))
        current = self._local_presence.get(key, 0) - 1
        if current <= 0:
            self._local_presence.pop(key, None)
            return 0
        self._local_presence[key] = current
        return current


event_bus = EventBus()


def room_channel(room_id: str) -> str:
    return f"room:{room_id}"


def user_channel(user_id: str) -> str:
    """Per-user pub/sub channel for realtime notification delivery (GAME-14)."""
    return f"user:{user_id}"
