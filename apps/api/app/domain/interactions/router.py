from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.auth.deps import CurrentUser, Session, Workspace, WorkspaceContext, require_role
from app.db.repositories.interactions import InteractionFilters
from app.domain.common import Page
from app.domain.interactions import service
from app.domain.interactions.schemas import InteractionCreate, InteractionRead, InteractionUpdate

router = APIRouter(prefix="/interactions", tags=["interactions"])
Member = Annotated[WorkspaceContext, Depends(require_role("member"))]


@router.get("", operation_id="interactions_list", response_model=Page[InteractionRead])
async def interactions_list(
    ws: Workspace,
    session: Session,
    contact_id: Annotated[UUID | None, Query()] = None,
    kind: Annotated[str | None, Query()] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query()] = None,
) -> Page[InteractionRead]:
    f = InteractionFilters(contact_id=contact_id, kind=kind, since=since, until=until)
    return await service.list_interactions(session, ws, f, limit, cursor)


@router.post("", operation_id="interactions_create", response_model=InteractionRead, status_code=201)
async def interactions_create(body: InteractionCreate, ctx: CurrentUser, ws: Member, session: Session) -> InteractionRead:
    return await service.create_interaction(session, ws, UUID(ctx.user_id), body)


@router.patch("/{interaction_id}", operation_id="interactions_update", response_model=InteractionRead)
async def interactions_update(
    interaction_id: UUID, body: InteractionUpdate, ctx: CurrentUser, ws: Member, session: Session
) -> InteractionRead:
    return await service.update_interaction(session, ws, UUID(ctx.user_id), interaction_id, body)


@router.delete("/{interaction_id}", operation_id="interactions_delete", status_code=204)
async def interactions_delete(interaction_id: UUID, ctx: CurrentUser, ws: Member, session: Session) -> Response:
    await service.delete_interaction(session, ws, UUID(ctx.user_id), interaction_id)
    return Response(status_code=204)
