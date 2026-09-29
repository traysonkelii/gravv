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
from app.jobs import queue
from app.jobs.runner import run_job
from app.observability import configure_logging

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
    background = [asyncio.create_task(_listener(wake, stop)), asyncio.create_task(_housekeeping(stop))]
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


if __name__ == "__main__":
    asyncio.run(main())
