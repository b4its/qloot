"""Realtime event bus: Redis pub/sub with an in-process fallback.

Used for live room leaderboards and presence. Degrades gracefully when Redis
is unavailable (single-process dev/test).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("realtime")


class EventBus:
    def __init__(self) -> None:
        self._redis = None
        self._local_subscribers: dict[str, set[asyncio.Queue]] = {}

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
                await self._redis.aclose()

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
                    await pubsub.aclose()
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


event_bus = EventBus()


def room_channel(room_id: str) -> str:
    return f"room:{room_id}"
