"""Blockchain worker: drains the transaction outbox and submits txs.

Run as: `python -m app.workers.blockchain`.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from datetime import UTC, datetime

from sqlalchemy import select

from app.blockchain.worker_logic import process_outbox_item
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope
from app.models.wallet import TransactionOutbox

log = get_logger("blockchain_worker")

_shutdown = asyncio.Event()

TOPICS = ("reward", "xp", "badge", "withdrawal", "pause", "unpause")


async def _claim(session) -> TransactionOutbox | None:
    stmt = (
        select(TransactionOutbox)
        .where(TransactionOutbox.status == "pending")
        .where(TransactionOutbox.topic.in_(TOPICS))
        .where(TransactionOutbox.available_at <= datetime.now(UTC))
        .order_by(TransactionOutbox.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _process_once() -> bool:
    async with session_scope() as session:
        item = await _claim(session)
        if item is None:
            return False
        # pause/unpause are handled at contract level; in dry-run we just mark done.
        if item.topic in ("pause", "unpause"):
            item.status = "done"
            item.processed_at = datetime.now(UTC)
            await session.flush()
            log.info("contract_control", action=item.topic)
            return True
        return await process_outbox_item(session, item.id)


async def run() -> None:
    configure_logging()
    log.info("blockchain_worker_started", dry_run=settings.blockchain_dry_run)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown.set)
        except NotImplementedError:  # pragma: no cover
            pass

    while not _shutdown.is_set():
        try:
            processed = await _process_once()
        except Exception as exc:  # noqa: BLE001
            log.error("blockchain_worker_error", error=str(exc))
            processed = False
        if not processed:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(_shutdown.wait(), timeout=settings.blockchain_poll_seconds)
    log.info("blockchain_worker_stopped")


if __name__ == "__main__":
    asyncio.run(run())
