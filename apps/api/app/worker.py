"""Worker entrypoint: python -m app.worker. Polls the jobs table, wakes on NOTIFY, reaps stale locks."""

import asyncio
import contextlib
import os
import signal
import socket
from typing import Any

import asyncpg
import structlog

from app.config import get_settings
from app.db.session import worker_session
from app.jobs import queue, scheduler
from app.jobs.runner import run_job
from app.observability import configure_logging
from app.worker_health import serve as serve_health

log = structlog.get_logger()


def _asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _listener(wake: asyncio.Event, stop: asyncio.Event) -> None:
    """Dedicated session-mode connection that LISTENs for enqueue notifications."""
    settings = get_settings()
    while not stop.is_set():
        try:
            conn = await asyncpg.connect(_asyncpg_dsn(settings.database_url_worker))
            await conn.add_listener("gravv_jobs", lambda *_: wake.set())
            log.info("worker_listening")
            await stop.wait()
            await conn.close()
        except Exception as exc:
            log.warning("worker_listener_error", error=str(exc))
            await asyncio.sleep(5)


async def _housekeeping(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            async with worker_session() as session:
                reaped = await queue.reap_stale(session)
                depth = await queue.queue_depth(session)
            log.info("jobs_queue_depth", jobs_queue_depth=depth, jobs_reaped=reaped)
        except Exception as exc:
            log.warning("worker_housekeeping_error", error=str(exc))
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=60)


async def drain(budget_seconds: float, worker_id: str = "lambda") -> int:
    """One scheduled pass (D-039, Lambda): reap stale locks, run the scheduler, then claim and run jobs one at a
    time until the queue is empty or the budget is spent. Returns the number of jobs run."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + budget_seconds
    async with worker_session() as session:
        reaped = await queue.reap_stale(session)
    enqueued = await scheduler.tick()
    ran = 0
    # ponytail: sequential; run under a semaphore like main() if one user's captures start queueing up.
    while loop.time() < deadline:
        async with worker_session() as session:
            job = await queue.claim(session, worker_id)
        if job is None:
            break
        await run_job(job)
        ran += 1
    async with worker_session() as session:
        depth = await queue.queue_depth(session)
    log.info("jobs_queue_depth", jobs_queue_depth=depth, jobs_reaped=reaped, jobs_run=ran, jobs_enqueued=enqueued)
    return ran


async def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    stop = asyncio.Event()
    wake = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    sem = asyncio.Semaphore(settings.worker_concurrency)
    tasks: set[asyncio.Task[Any]] = set()
    health = await serve_health(settings.worker_health_port) if settings.app_env in ("staging", "production") else None
    background = [
        asyncio.create_task(_listener(wake, stop)),
        asyncio.create_task(_housekeeping(stop)),
        asyncio.create_task(scheduler.run(stop)),
    ]
    log.info("worker_started", worker_id=worker_id, concurrency=settings.worker_concurrency)

    async def _run(job: queue.Job) -> None:
        async with sem:
            await run_job(job)

    while not stop.is_set():
        claimed = None
        if not sem.locked():
            try:
                async with worker_session() as session:
                    claimed = await queue.claim(session, worker_id)
            except Exception as exc:
                log.warning("worker_claim_error", error=str(exc))
                await asyncio.sleep(settings.worker_poll_interval_seconds)
                continue
        if claimed is not None:
            task = asyncio.create_task(_run(claimed))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
            continue
        wake.clear()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(wake.wait(), timeout=settings.worker_poll_interval_seconds)

    log.info("worker_stopping", in_flight=len(tasks))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    for task in background:
        task.cancel()
    await asyncio.gather(*background, return_exceptions=True)
    if health is not None:
        health.close()


if __name__ == "__main__":
    asyncio.run(main())
