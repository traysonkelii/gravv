from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import text

from app.auth.deps import CurrentUser, Session
from app.domain.captures.schemas import JobRead
from app.errors import Problem

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", operation_id="jobs_get", response_model=JobRead)
async def jobs_get(job_id: UUID, ctx: CurrentUser, session: Session) -> JobRead:
    row = (await session.execute(text("select * from get_job(:id)"), {"id": job_id})).mappings().first()
    if row is None:
        raise Problem(404, "not_found", "Job not found")
    error = row["last_error"]
    return JobRead(
        id=row["id"],
        kind=row["kind"],
        status=str(row["status"]),
        result=row["result"],
        last_error=error.split("\n")[0][:200] if error else None,
        created_at=row["created_at"],
        finished_at=row["finished_at"],
    )
