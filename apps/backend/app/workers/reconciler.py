"""Ledger reconciliation worker.

Periodically scans OPT accounts for cached-vs-ledger drift, repairs the cached
balance, and reports it (metric + log). Run as:

    python -m app.workers.reconciler
"""

from __future__ import annotations

import asyncio
import contextlib
import signal

from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope
from app.services.reward_engine import RewardEngine

log = get_logger("reconciler")

_shutdown = asyncio.Event()

# How often to sweep (seconds). Kept configurable via env-less constant so the
# worker is dependency-light; override by editing here or wrapping in a cron.
RECONCILE_INTERVAL_SECONDS = 300


async def reconcile_once() -> int:
    """Run one reconciliation sweep. Returns the number of drifted accounts."""
    async with session_scope() as session:
        drifted = await RewardEngine(session).reconcile_all()
    if drifted:
        log.warning("ledger_drift_repaired", count=len(drifted))
    return len(drifted)


async def run() -> None:
    configure_logging()
    log.info("reconciler_started", interval=RECONCILE_INTERVAL_SECONDS)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown.set)
        except NotImplementedError:  # pragma: no cover
            pass

    while not _shutdown.is_set():
        try:
            await reconcile_once()
        except Exception as exc:  # noqa: BLE001
            log.error("reconciler_error", error=str(exc))
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(_shutdown.wait(), timeout=RECONCILE_INTERVAL_SECONDS)
    log.info("reconciler_stopped")


if __name__ == "__main__":
    asyncio.run(run())
