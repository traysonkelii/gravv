"""Recurring job enqueueing inside the worker. One worker at a time holds the advisory lock (Section 7.6).

Schedule (UTC): scores.compute 02:00 daily per workspace, insights.generate 02:30 daily per workspace,
profile.synthesize hourly for stale profiles (max 50 per workspace), retention.purge weekly (Sunday 03:00)."""

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text

from app.db.session import worker_session
from app.jobs import queue
from app.jobs.handlers import HANDLERS

log = structlog.get_logger()
LOCK_KEY = 7_204_112_001


async def _due_today(session: Any, key: str) -> bool:
    return bool(
        await session.scalar(
            text("select exists (select 1 from jobs where dedupe_key = :k and created_at >= date_trunc('day', now()))"),
            {"k": key},
        )
    )


async def tick(now: datetime | None = None) -> int:
    """Runs one scheduler pass; returns the number of jobs enqueued. Safe to call repeatedly."""
    now = now or datetime.now(UTC)
    enqueued = 0
    async with worker_session() as s:
        got = await s.scalar(text("select pg_try_advisory_xact_lock(:k)"), {"k": LOCK_KEY})
        if not got:
            return 0
        workspaces: list[Any] = list((await s.execute(text("select id from workspaces"))).scalars().all())
        day = now.strftime("%Y-%m-%d")
        for ws in workspaces:
            if now.hour >= 2:
                key = f"scores.compute:{ws}:{day}"
                if not await _due_today(s, key) and await queue.enqueue_as_worker(
                    s, "scores.compute", {"workspace_id": str(ws)}, ws, None, 6, key
                ):
                    enqueued += 1
            if (now.hour >= 2 and now.minute >= 30) or now.hour >= 3:
                key = f"insights.generate:{ws}:{day}"
                if not await _due_today(s, key) and await queue.enqueue_as_worker(
                    s, "insights.generate", {"workspace_id": str(ws)}, ws, None, 6, key
                ):
                    enqueued += 1
            stale_rows = await s.execute(
                text(
                    "select p.contact_id from contact_profiles p join contacts c on c.id = p.contact_id "
                    "where c.workspace_id = :ws and p.stale and c.deleted_at is null "
                    "and exists (select 1 from interactions i where i.contact_id = c.id and i.deleted_at is null) "
                    "order by p.updated_at limit 50"
                ),
                {"ws": ws},
            )
            stale: list[Any] = [r[0] for r in stale_rows.all()]
            for cid in stale:
                key = f"profile.synthesize:{cid}"
                if await queue.enqueue_as_worker(s, "profile.synthesize", {"contact_id": str(cid)}, ws, None, 7, key):
                    enqueued += 1
        if "retention.purge" in HANDLERS and now.weekday() == 6 and now.hour >= 3:
            key = f"retention.purge:{now.strftime('%Y-W%W')}"
            if not await _due_today(s, key) and await queue.enqueue_as_worker(s, "retention.purge", {}, None, None, 8, key):
                enqueued += 1
    return enqueued


async def run(stop: asyncio.Event, interval_seconds: float = 60.0) -> None:
    while not stop.is_set():
        try:
            n = await tick()
            if n:
                log.info("scheduler_enqueued", jobs=n)
        except Exception as exc:
            log.warning("scheduler_error", error=str(exc))
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
