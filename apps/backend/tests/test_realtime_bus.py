"""EventBus unit coverage: local-fallback pub/sub, backpressure/drop policy,
and the presence connection counter (supports GAME-06/09).
"""

from __future__ import annotations

import asyncio

from app.services.realtime import EventBus


async def test_local_fallback_delivers_published_messages():
    bus = EventBus()  # no Redis connection attempted -> local fallback only
    channel = "room:test-local"

    received: list[dict] = []

    async def _reader():
        async for msg in bus.subscribe(channel):
            received.append(msg)
            if len(received) == 2:
                return

    task = asyncio.create_task(_reader())
    await asyncio.sleep(0.01)  # let the subscriber register before publishing
    await bus.publish(channel, {"type": "a"})
    await bus.publish(channel, {"type": "b"})
    await asyncio.wait_for(task, timeout=1)

    assert received == [{"type": "a"}, {"type": "b"}]


async def test_publish_with_no_subscriber_does_not_raise():
    bus = EventBus()
    # No one is subscribed to this channel; publishing must be a no-op, not
    # an error (a slow/absent consumer must never crash the publisher).
    await bus.publish("room:nobody-listening", {"type": "x"})


async def test_local_queue_drops_silently_when_full():
    """A slow consumer's queue (maxsize=100) must not block or crash the
    publisher — excess messages are dropped, matching the documented
    backpressure policy (GAME-09).
    """
    bus = EventBus()
    channel = "room:backpressure"

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    bus._local_subscribers.setdefault(channel, set()).add(queue)  # noqa: SLF001

    # Publish well past the queue's capacity; none of this should raise.
    for i in range(150):
        await bus.publish(channel, {"type": "tick", "i": i})

    assert queue.qsize() == 100  # capped, not unbounded
    # The oldest messages were dropped (FIFO queue never evicts existing
    # items to make room) — the first item in the queue is not #0.
    first = queue.get_nowait()
    assert first["i"] == 0  # items already enqueued before overflow remain


async def test_dropped_frames_inject_a_resync_hint():
    """GAME-09: once a subscriber's queue overflows, the *next* read of that
    queue via subscribe() must yield a 'resync' hint before the next real
    message, so the client knows to reload rather than trust a silent gap.
    """
    bus = EventBus()
    channel = "room:resync"

    gen = bus.subscribe(channel)
    # Prime the generator so its queue is registered before we publish.
    task = asyncio.ensure_future(gen.__anext__())
    await asyncio.sleep(0.01)

    # Force an overflow by directly marking the queue as having dropped a
    # message (simulating a full queue without actually filling 100 slots).
    (queue,) = bus._local_subscribers[channel]  # noqa: SLF001
    bus._dropped_channels.add(id(queue))  # noqa: SLF001
    await bus.publish(channel, {"type": "real_message"})

    first = await task
    assert first["type"] == "resync"
    assert first["reason"] == "backpressure"

    second = await gen.__anext__()
    assert second["type"] == "real_message"
    await gen.aclose()


async def test_connection_counter_increments_and_decrements():
    bus = EventBus()
    key = "room-1:user-1"

    assert await bus.incr_connection(key) == 1
    assert await bus.incr_connection(key) == 2
    assert await bus.decr_connection(key) == 1
    assert await bus.decr_connection(key) == 0


async def test_connection_counter_floors_at_zero():
    bus = EventBus()
    key = "room-2:user-2"

    # Decrementing a counter that was never incremented must not go negative
    # (a duplicate/late disconnect must never under-flow the count).
    assert await bus.decr_connection(key) == 0
    assert await bus.decr_connection(key) == 0


async def test_connection_counter_is_scoped_per_key():
    bus = EventBus()
    assert await bus.incr_connection("room-a:user-x") == 1
    # A different room/user pair starts its own independent count.
    assert await bus.incr_connection("room-b:user-x") == 1
    assert await bus.decr_connection("room-a:user-x") == 0
    # room-b's counter is untouched by room-a's decrement.
    assert await bus.incr_connection("room-b:user-x") == 2
