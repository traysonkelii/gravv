"""Re-queues a dead or failed job. Usage: uv run python -m scripts.requeue_job <job id>"""

import asyncio
import sys
import uuid

from sqlalchemy import text

from app.db.session import worker_session


async def main(job_id: uuid.UUID) -> None:
    async with worker_session() as s:
        row = (
            await s.execute(text("select kind, status::text, attempts, max_attempts, last_error from jobs where id = :id"), {"id": job_id})
        ).first()
        if row is None:
            print("job not found")
            return
        await s.execute(
            text(
                "update jobs set status = 'queued', run_after = now(), attempts = 0, last_error = null, "
                "locked_by = null, locked_at = null where id = :id"
            ),
            {"id": job_id},
        )
    print(f"re-queued {row[0]} (was {row[1]} after {row[2]}/{row[3]} attempts): {(row[4] or '')[:200]}")


if __name__ == "__main__":
    asyncio.run(main(uuid.UUID(sys.argv[1])))
