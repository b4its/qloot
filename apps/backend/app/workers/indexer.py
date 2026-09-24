"""Blockchain indexer: polls confirmations and marks rewards confirmed.

Run as: `python -m app.workers.indexer`.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal

from app.blockchain.worker_logic import (
    refresh_confirmations,
    resubmit_stuck_transactions,
    revalidate_confirmed_transactions,
)
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope

log = get_logger("indexer")

_shutdown = asyncio.Event()


async def run() -> None:
    configure_logging()
    log.info("indexer_started", confirmations=settings.opc_confirmations)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown.set)
        except NotImplementedError:  # pragma: no cover
            pass

    while not _shutdown.is_set():
        try:
            async with session_scope() as session:
                # WEB3-07: roll back confirmed txs dropped by a reorg first.
                await revalidate_confirmed_transactions(session)
                # WEB3-06b: resubmit stuck txs before refreshing confirmations so
                # a replacement has a chance to be mined in the same cycle.
                await resubmit_stuck_transactions(session)
                n = await refresh_confirmations(session)
            if n:
                log.info("confirmations_refreshed", count=n)
        except Exception as exc:  # noqa: BLE001
            log.error("indexer_error", error=str(exc))
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(_shutdown.wait(), timeout=settings.blockchain_poll_seconds)
    log.info("indexer_stopped")


if __name__ == "__main__":
    asyncio.run(run())
