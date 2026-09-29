"""Runs one claimed job to completion. Shared by the worker loop and by tests (run_job_now)."""

from uuid import UUID

import structlog

from app.db.session import worker_session
from app.jobs import queue
from app.jobs.handlers import HANDLERS
from app.jobs.queue import Job

log = structlog.get_logger()


async def run_job(job: Job) -> str:
    """Executes the handler and records the outcome. Returns the final job status."""
    handler = HANDLERS.get(job.kind)
    try:
        if handler is None:
            raise LookupError(f"no handler for job kind {job.kind}")
        result = await handler(job)
    except Exception as exc:
        log.warning("job_failed", job_id=str(job.id), kind=job.kind, attempts=job.attempts, error=str(exc)[:500])
        async with worker_session() as session:
            status = await queue.fail(session, job, f"{type(exc).__name__}: {exc}")
        if status == "dead":
            log.error("job_dead", job_id=str(job.id), kind=job.kind)
        return status
    async with worker_session() as session:
        await queue.complete(session, job.id, result)
    log.info("job_succeeded", job_id=str(job.id), kind=job.kind)
    return "succeeded"


async def run_job_now(job_id: UUID, wait_seconds: float = 15.0) -> str:
    """Test helper: claims a specific job and runs it inline. If a live worker already claimed it, waits for
    that run to finish and returns its status instead, so tests behave the same with or without `make dev`."""
    import asyncio

    from sqlalchemy import text

    async with worker_session() as session:
        job = await queue.claim_by_id(session, job_id, "inline")
    if job is not None:
        return await run_job(job)
    deadline = asyncio.get_running_loop().time() + wait_seconds
    while True:
        async with worker_session() as session:
            status = await session.scalar(text("select status::text from jobs where id = :id"), {"id": job_id})
        if status is None:
            raise LookupError(f"job {job_id} does not exist")
        if status in ("succeeded", "failed", "dead"):
            return str(status)
        if status == "queued":
            async with worker_session() as session:
                job = await queue.claim_by_id(session, job_id, "inline")
            if job is not None:
                return await run_job(job)
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError(f"job {job_id} still {status} after {wait_seconds}s")
        await asyncio.sleep(0.2)
