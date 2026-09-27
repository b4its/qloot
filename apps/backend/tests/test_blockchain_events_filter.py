"""Admin blockchain events listing with an exact event-name filter.

The indexer writes ``blockchain_events`` rows; operators trace a specific event
type (e.g. ``RewardPaid``) via the ``name`` filter rather than paging the whole
feed.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _admin(client, email="admin_evt@ex.com"):
    from tests.helpers import register_actor

    return await register_actor(client, email, "admin", full_name="Admin Events")


async def _seed_events(client, tag: str = "11") -> list[str]:
    """Insert a couple of indexed events directly through the session.

    Returns the transaction hashes so the test can clean them up — the shared
    test database persists rows across tests, and some worker tests assert on
    the *total* number of ``blockchain_events``. Unique hashes per test keep the
    (transaction_hash, log_index) constraint satisfied.
    """
    sm = client._sm  # type: ignore[attr-defined]
    from app.models.wallet import BlockchainEvent

    hashes = ["0x" + tag * 32, "0x" + ("f" + tag[1:]) * 32]
    async with sm() as s:
        s.add(
            BlockchainEvent(
                contract_address="0x" + "a" * 40,
                event_name="RewardPaid",
                transaction_hash=hashes[0],
                log_index=1,
                block_number=100,
                args={"amount": 10},
            )
        )
        s.add(
            BlockchainEvent(
                contract_address="0x" + "a" * 40,
                event_name="Transfer",
                transaction_hash=hashes[1],
                log_index=2,
                block_number=101,
                args={"value": 5},
            )
        )
        await s.commit()
    return hashes


async def _cleanup(client, hashes: list[str]) -> None:
    sm = client._sm  # type: ignore[attr-defined]
    from sqlalchemy import delete

    from app.models.wallet import BlockchainEvent

    async with sm() as s:
        await s.execute(delete(BlockchainEvent).where(BlockchainEvent.transaction_hash.in_(hashes)))
        await s.commit()


async def test_name_filter_returns_only_that_event(client):
    await _admin(client)
    hashes = await _seed_events(client, "11")
    try:
        r = await client.get("/api/v1/blockchain/events?name=RewardPaid")
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) >= 1
        assert all(row["name"] == "RewardPaid" for row in rows)
        # The args payload is passed through for the detail view.
        assert all("args" in row for row in rows)
    finally:
        await _cleanup(client, hashes)


async def test_events_list_returns_all_names_without_filter(client):
    await _admin(client, "admin_evt_all@ex.com")
    hashes = await _seed_events(client, "33")
    try:
        r = await client.get("/api/v1/blockchain/events?limit=200")
        assert r.status_code == 200, r.text
        names = {row["name"] for row in r.json()}
        assert {"RewardPaid", "Transfer"} <= names
    finally:
        await _cleanup(client, hashes)
