from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.auth.deps import CurrentUser, Session, Workspace
from app.domain.analytics import service
from app.domain.analytics.schemas import (
    AnalyticsSummary,
    BandCount,
    MemberMetrics,
    Range,
    Scope,
    SeriesPoint,
    TopContact,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", operation_id="analytics_summary", response_model=AnalyticsSummary)
async def analytics_summary(
    ctx: CurrentUser, ws: Workspace, session: Session, range: Range = "month", scope: Scope = "me"
) -> AnalyticsSummary:
    return await service.summary(session, ws, UUID(ctx.user_id), range, scope)


@router.get("/distribution", operation_id="analytics_distribution", response_model=list[BandCount])
async def analytics_distribution(ctx: CurrentUser, ws: Workspace, session: Session, scope: Scope = "me") -> list[BandCount]:
    return await service.distribution(session, ws, UUID(ctx.user_id), scope)


@router.get("/interactions", operation_id="analytics_interactions", response_model=list[SeriesPoint])
async def analytics_interactions(
    ctx: CurrentUser, ws: Workspace, session: Session, range: Range = "month", scope: Scope = "me"
) -> list[SeriesPoint]:
    return await service.interactions_series(session, ws, UUID(ctx.user_id), range, scope)


@router.get("/top-contacts", operation_id="analytics_top_contacts", response_model=list[TopContact])
async def analytics_top_contacts(
    ctx: CurrentUser,
    ws: Workspace,
    session: Session,
    scope: Scope = "me",
    q: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[TopContact]:
    return await service.top_contacts(session, ws, UUID(ctx.user_id), scope, q, limit)


@router.get("/team", operation_id="analytics_team", response_model=list[MemberMetrics])
async def analytics_team(ws: Workspace, session: Session, range: Range = "month") -> list[MemberMetrics]:
    return await service.team(session, ws, range)
