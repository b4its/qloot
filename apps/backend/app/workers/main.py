"""Background worker: drains AI grading jobs and generation jobs.

Runs as a separate process: `python -m app.workers.main`.
Uses a simple polling loop with SKIP LOCKED so multiple replicas are safe.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope
from app.models.exam import GradingJob
from app.services.grading_service import process_grading_job
from app.services.material_service import MaterialService

log = get_logger("worker")

_shutdown = asyncio.Event()


async def _claim_job(session) -> GradingJob | None:
    stmt = (
        select(GradingJob)
        .where(GradingJob.status == "queued")
        .where(GradingJob.available_at <= datetime.now(UTC))
        .order_by(GradingJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _process_once() -> bool:
    async with session_scope() as session:
        job = await _claim_job(session)
        if job is None:
            return False
        if job.kind == "grading":
            ok = await process_grading_job(session, job.id)
        elif job.kind == "generation":
            job.status = "running"
            job.started_at = datetime.now(UTC)
            job.attempts += 1
            await session.flush()
            try:
                await MaterialService(session).run_generation(job)
                job.status = "done"
                job.finished_at = datetime.now(UTC)
                ok = True
            except Exception as exc:  # noqa: BLE001
                job.attempts += 1
                job.error_code = "generation_error"
                job.error_message = str(exc)
                job.status = "failed" if job.attempts >= job.max_attempts else "queued"
                ok = False
            await session.flush()
        else:
            job.status = "failed"
            job.error_code = "unknown_kind"
            await session.flush()
            ok = False
        return ok


async def run() -> None:
    configure_logging()
    log.info("worker_started", poll=settings.blockchain_poll_seconds)

    def _stop(*_: object) -> None:
        _shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:  # pragma: no cover
            pass

    while not _shutdown.is_set():
        try:
            processed = await _process_once()
        except Exception as exc:  # noqa: BLE001
            log.error("worker_iteration_failed", error=str(exc))
            processed = False
        if not processed:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(_shutdown.wait(), timeout=settings.blockchain_poll_seconds)
    log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(run())
