from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.auth.deps import CurrentUser, Session, Workspace, WorkspaceContext, require_role
from app.domain.common import Page
from app.domain.opportunities import service
from app.domain.opportunities.schemas import OpportunityContactPut, OpportunityCreate, OpportunityRead, OpportunityUpdate

router = APIRouter(prefix="/opportunities", tags=["opportunities"])
Member = Annotated[WorkspaceContext, Depends(require_role("member"))]


@router.get("", operation_id="opportunities_list", response_model=Page[OpportunityRead])
async def opportunities_list(
    ctx: CurrentUser,
    ws: Workspace,
    session: Session,
    status: Annotated[str | None, Query(pattern="^(open|won|lost|on_hold)$")] = None,
    company_id: Annotated[UUID | None, Query()] = None,
    owner: Annotated[str | None, Query(pattern="^me$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query()] = None,
) -> Page[OpportunityRead]:
    return await service.list_opportunities(session, ws, UUID(ctx.user_id), status, company_id, owner == "me", limit, cursor)


@router.post("", operation_id="opportunities_create", response_model=OpportunityRead, status_code=201)
async def opportunities_create(body: OpportunityCreate, ctx: CurrentUser, ws: Member, session: Session) -> OpportunityRead:
    return await service.create(session, ws, UUID(ctx.user_id), body)


@router.get("/{opportunity_id}", operation_id="opportunities_get", response_model=OpportunityRead)
async def opportunities_get(opportunity_id: UUID, ws: Workspace, session: Session) -> OpportunityRead:
    return await service.get(session, ws, opportunity_id)


@router.patch("/{opportunity_id}", operation_id="opportunities_update", response_model=OpportunityRead)
async def opportunities_update(
    opportunity_id: UUID, body: OpportunityUpdate, ctx: CurrentUser, ws: Member, session: Session
) -> OpportunityRead:
    return await service.update(session, ws, UUID(ctx.user_id), opportunity_id, body)


@router.delete("/{opportunity_id}", operation_id="opportunities_delete", status_code=204)
async def opportunities_delete(opportunity_id: UUID, ctx: CurrentUser, ws: Member, session: Session) -> Response:
    await service.delete(session, ws, UUID(ctx.user_id), opportunity_id)
    return Response(status_code=204)


@router.put("/{opportunity_id}/contacts/{contact_id}", operation_id="opportunity_contacts_put", response_model=OpportunityRead)
async def opportunity_contacts_put(
    opportunity_id: UUID, contact_id: UUID, body: OpportunityContactPut, ws: Member, session: Session
) -> OpportunityRead:
    return await service.put_contact(session, ws, opportunity_id, contact_id, body.role.value)


@router.delete("/{opportunity_id}/contacts/{contact_id}", operation_id="opportunity_contacts_delete", response_model=OpportunityRead)
async def opportunity_contacts_delete(opportunity_id: UUID, contact_id: UUID, ws: Member, session: Session) -> OpportunityRead:
    return await service.delete_contact(session, ws, opportunity_id, contact_id)
