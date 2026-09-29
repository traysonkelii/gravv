from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.db.session import worker_session
from app.jobs import queue
from app.jobs.runner import run_job, run_job_now
from tests.conftest import AuthAdmin, create_org, rls_session

# A live worker may be running against the same database; a far-future run_after keeps these jobs
# out of its claim query while run_job_now / claim_by_id ignore run_after.
LATER = datetime.now(UTC) + timedelta(hours=1)


async def test_noop_job_round_trip(auth_admin: AuthAdmin) -> None:
    user = await auth_admin.create_user("w", "Worker Tester")
    ws = await create_org(user, "Org W")
    async with rls_session(user) as s:
        job_id = await queue.enqueue(s, "noop", {"hello": "world"}, ws, run_after=LATER, dedupe_key=f"noop:{ws}")
        assert job_id is not None
        again = await queue.enqueue(s, "noop", {"hello": "again"}, ws, run_after=LATER, dedupe_key=f"noop:{ws}")
        assert again is None, "dedupe_key must suppress a duplicate while queued"
    assert await run_job_now(job_id) == "succeeded"
    async with worker_session() as s:
        row = (await s.execute(text("select status::text, result from jobs where id = :id"), {"id": job_id})).first()
    assert row is not None and row[0] == "succeeded" and row[1] == {"echo": {"hello": "world"}}


async def test_unknown_kind_backs_off_then_dies(auth_admin: AuthAdmin) -> None:
    user = await auth_admin.create_user("w2", "Worker Tester")
    ws = await create_org(user, "Org W2")
    async with rls_session(user) as s:
        job_id = await queue.enqueue(s, "does.not.exist", {}, ws, run_after=LATER)
    assert job_id is not None
    async with worker_session() as s:
        await s.execute(text("update jobs set max_attempts = 2 where id = :id"), {"id": job_id})
    assert await run_job_now(job_id) == "queued"
    async with worker_session() as s:
        job = await queue.claim_by_id(s, job_id, "test")
    assert job is not None and job.attempts == 2
    assert await run_job(job) == "dead"
