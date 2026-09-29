from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.auth.deps import CurrentUser, Session, Workspace, WorkspaceContext, require_role
from app.domain.captures.schemas import JobAccepted
from app.domain.insights import service
from app.domain.insights.schemas import InsightActResult, InsightRead, InsightStatusUpdate

router = APIRouter(prefix="/insights", tags=["insights"])
Member = Annotated[WorkspaceContext, Depends(require_role("member"))]
Manager = Annotated[WorkspaceContext, Depends(require_role("manager"))]


@router.get("", operation_id="insights_list", response_model=list[InsightRead])
async def insights_list(
    ctx: CurrentUser,
    ws: Workspace,
    session: Session,
    status: Annotated[str | None, Query(pattern="^(new|seen|acted|dismissed|expired)$")] = None,
    kind: Annotated[str | None, Query()] = None,
    contact_id: Annotated[UUID | None, Query()] = None,
    scope: Annotated[str, Query(pattern="^(me|team)$")] = "me",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[InsightRead]:
    return await service.list_insights(session, ws, UUID(ctx.user_id), status, kind, contact_id, scope, limit)


@router.post("/{insight_id}/status", operation_id="insights_set_status", response_model=InsightRead)
async def insights_set_status(insight_id: UUID, body: InsightStatusUpdate, ws: Workspace, session: Session) -> InsightRead:
    return await service.set_status(session, ws, insight_id, body.status)


@router.post("/{insight_id}/act", operation_id="insights_act", response_model=InsightActResult)
async def insights_act(insight_id: UUID, ctx: CurrentUser, ws: Member, session: Session) -> InsightActResult:
    return await service.act(session, ws, UUID(ctx.user_id), insight_id)


@router.post("/generate", operation_id="insights_generate_now", response_model=JobAccepted, status_code=202)
async def insights_generate_now(ws: Manager, session: Session) -> JobAccepted:
    job_id = await service.generate_now(session, ws)
    return JobAccepted(job_id=job_id, deduplicated=job_id is None)
