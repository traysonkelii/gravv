from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.auth.deps import CurrentUser, Session, Workspace, WorkspaceContext, require_role
from app.domain.facts import service
from app.domain.facts.schemas import FactCreate, FactRead, FactUpdate

router = APIRouter(tags=["facts"])
Member = Annotated[WorkspaceContext, Depends(require_role("member"))]


@router.get("/contacts/{contact_id}/facts", operation_id="facts_list", response_model=list[FactRead])
async def facts_list(
    contact_id: UUID, ws: Workspace, session: Session, include_inactive: Annotated[bool, Query()] = False
) -> list[FactRead]:
    return await service.list_facts(session, ws, contact_id, include_inactive)


@router.post("/contacts/{contact_id}/facts", operation_id="facts_create", response_model=FactRead, status_code=201)
async def facts_create(contact_id: UUID, body: FactCreate, ctx: CurrentUser, ws: Member, session: Session) -> FactRead:
    return await service.create_fact(session, ws, UUID(ctx.user_id), contact_id, body)


@router.patch("/facts/{fact_id}", operation_id="facts_update", response_model=FactRead)
async def facts_update(fact_id: UUID, body: FactUpdate, ctx: CurrentUser, ws: Member, session: Session) -> FactRead:
    return await service.update_fact(session, ws, UUID(ctx.user_id), fact_id, body)


@router.delete("/facts/{fact_id}", operation_id="facts_delete", status_code=204)
async def facts_delete(fact_id: UUID, ws: Member, session: Session) -> Response:
    await service.delete_fact(session, ws, fact_id)
    return Response(status_code=204)
