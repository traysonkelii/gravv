"""Postgres job queue: enqueue through the SQL function, claim with SKIP LOCKED, complete or fail with backoff."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BACKOFF_SECONDS = [30, 120, 600, 3600, 21600]
STALE_LOCK_MINUTES = 15


@dataclass(frozen=True)
class Job:
    id: UUID
    kind: str
    payload: dict[str, Any]
    workspace_id: UUID | None
    user_id: UUID | None
    attempts: int
    max_attempts: int


_CLAIM = text("""
with next as (
  select id from jobs
  where status = 'queued' and run_after <= now()
  order by priority, run_after
  for update skip locked
  limit 1
)
update jobs j set status = 'running', locked_by = :worker_id, locked_at = now(),
                  started_at = coalesce(started_at, now()), attempts = attempts + 1
from next where j.id = next.id
returning j.id, j.kind, j.payload, j.workspace_id, j.user_id, j.attempts, j.max_attempts
""")

_CLAIM_ONE = text("""
update jobs j set status = 'running', locked_by = :worker_id, locked_at = now(),
                  started_at = coalesce(started_at, now()), attempts = attempts + 1
where j.id = :id and j.status = 'queued'
returning j.id, j.kind, j.payload, j.workspace_id, j.user_id, j.attempts, j.max_attempts
""")


def _row_to_job(row: Any) -> Job:
    return Job(
        id=row[0],
        kind=row[1],
        payload=row[2] or {},
        workspace_id=row[3],
        user_id=row[4],
        attempts=row[5],
        max_attempts=row[6],
    )


async def enqueue(
    session: AsyncSession,
    kind: str,
    payload: dict[str, Any],
    workspace_id: UUID | None,
    run_after: datetime | None = None,
    priority: int = 5,
    dedupe_key: str | None = None,
) -> UUID | None:
    """Runs under the caller's identity through the security definer function. Returns None when deduplicated."""
    result = await session.execute(
        text(
            "select enqueue_job(:kind, cast(:payload as jsonb), :ws, :run_after, cast(:priority as smallint), :dedupe)"
        ),
        {
            "kind": kind,
            "payload": json.dumps(payload),
            "ws": workspace_id,
            "run_after": run_after or datetime.now(UTC),
            "priority": priority,
            "dedupe": dedupe_key,
        },
    )
    return result.scalar_one_or_none()


async def enqueue_as_worker(
    session: AsyncSession,
    kind: str,
    payload: dict[str, Any],
    workspace_id: UUID | None,
    user_id: UUID | None,
    priority: int = 5,
    dedupe_key: str | None = None,
    run_after: datetime | None = None,
) -> UUID | None:
    """Worker-side enqueue (service_role): direct insert, same dedupe semantics as enqueue_job()."""
    result = await session.execute(
        text(
            "insert into jobs (kind, payload, workspace_id, user_id, run_after, priority, dedupe_key) "
            "values (:kind, cast(:payload as jsonb), :ws, :uid, :run_after, cast(:priority as smallint), :dedupe) "
            "on conflict (dedupe_key) where status in ('queued', 'running') and dedupe_key is not null do nothing "
            "returning id"
        ),
        {
            "kind": kind,
            "payload": json.dumps(payload, default=str),
            "ws": workspace_id,
            "uid": user_id,
            "run_after": run_after or datetime.now(UTC),
            "priority": priority,
            "dedupe": dedupe_key,
        },
    )
    job_id = result.scalar_one_or_none()
    await session.execute(text("select pg_notify('gravv_jobs', :id)"), {"id": str(job_id or "")})
    return job_id


async def claim(session: AsyncSession, worker_id: str) -> Job | None:
    row = (await session.execute(_CLAIM, {"worker_id": worker_id})).first()
    return _row_to_job(row) if row else None


async def claim_by_id(session: AsyncSession, job_id: UUID, worker_id: str) -> Job | None:
    row = (await session.execute(_CLAIM_ONE, {"id": job_id, "worker_id": worker_id})).first()
    return _row_to_job(row) if row else None


async def complete(session: AsyncSession, job_id: UUID, result: dict[str, Any] | None) -> None:
    await session.execute(
        text(
            "update jobs set status = 'succeeded', result = cast(:result as jsonb), finished_at = now(), "
            "locked_by = null, locked_at = null where id = :id"
        ),
        {"id": job_id, "result": json.dumps(result) if result is not None else None},
    )


async def fail(session: AsyncSession, job: Job, error: str) -> str:
    """Re-queues with backoff while attempts remain; otherwise marks the job dead. Returns the new status."""
    if job.attempts >= job.max_attempts:
        await session.execute(
            text(
                "update jobs set status = 'dead', last_error = :err, finished_at = now(), locked_by = null, "
                "locked_at = null where id = :id"
            ),
            {"id": job.id, "err": error[:2000]},
        )
        return "dead"
    delay = BACKOFF_SECONDS[min(job.attempts - 1, len(BACKOFF_SECONDS) - 1)]
    await session.execute(
        text(
            "update jobs set status = 'queued', last_error = :err, run_after = :run_after, locked_by = null, "
            "locked_at = null where id = :id"
        ),
        {"id": job.id, "err": error[:2000], "run_after": datetime.now(UTC) + timedelta(seconds=delay)},
    )
    return "queued"


async def heartbeat(session: AsyncSession, job_id: UUID) -> None:
    await session.execute(
        text("update jobs set locked_at = now() where id = :id and status = 'running'"), {"id": job_id}
    )


async def reap_stale(session: AsyncSession) -> int:
    result = await session.execute(
        text(
            "update jobs set status = 'queued', locked_by = null, locked_at = null "
            "where status = 'running' and locked_at < now() - make_interval(mins => :mins) returning id"
        ),
        {"mins": STALE_LOCK_MINUTES},
    )
    return len(result.all())


async def queue_depth(session: AsyncSession) -> int:
    return int(await session.scalar(text("select count(*) from jobs where status = 'queued'")) or 0)
