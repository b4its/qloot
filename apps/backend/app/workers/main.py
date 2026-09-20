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

from app.ai.provider import close_ai_provider
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


async def _reap_stuck_jobs(session) -> int:
    """Recover jobs left in 'running' by a crashed/restarted worker.

    A job stuck past the timeout is requeued (with backoff) or failed if it has
    exhausted its attempts, so it can never be lost forever.
    """
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(seconds=settings.worker_job_timeout_seconds)
    stmt = (
        select(GradingJob)
        .where(GradingJob.status == "running")
        .where(GradingJob.started_at.is_not(None))
        .where(GradingJob.started_at < cutoff)
        .limit(20)
        .with_for_update(skip_locked=True)
    )
    stuck = (await session.execute(stmt)).scalars().all()
    for job in stuck:
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.error_code = "timeout"
            job.error_message = "Job exceeded the worker timeout"
            job.finished_at = datetime.now(UTC)
        else:
            job.status = "queued"
            job.available_at = datetime.now(UTC) + timedelta(seconds=30)
    if stuck:
        await session.flush()
        log.warning("reaped_stuck_jobs", count=len(stuck))
    return len(stuck)


async def _process_once() -> bool:
    async with session_scope() as session:
        await _reap_stuck_jobs(session)
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
                job.error_code = None
                job.error_message = None
                ok = True
            except Exception as exc:  # noqa: BLE001
                job.error_code = "generation_error"
                job.error_message = str(exc)[:500]
                if job.attempts >= job.max_attempts:
                    job.status = "failed"
                    job.finished_at = datetime.now(UTC)
                else:
                    # Backoff so a failing generation does not hot-loop.
                    from datetime import timedelta

                    job.status = "queued"
                    job.available_at = datetime.now(UTC) + timedelta(
                        seconds=min(600, 2**job.attempts)
                    )
                ok = False
            await session.flush()
        else:
            job.status = "failed"
            job.error_code = "unknown_kind"
            job.finished_at = datetime.now(UTC)
            await session.flush()
            ok = False
        return ok


async def run() -> None:
    configure_logging()
    log.info("worker_started", poll=settings.worker_poll_seconds)

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
                await asyncio.wait_for(_shutdown.wait(), timeout=settings.worker_poll_seconds)
    await close_ai_provider()
    log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(run())
