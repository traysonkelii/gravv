from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.auth.deps import CurrentUser, Session, Workspace, WorkspaceContext, require_role
from app.db.repositories.contacts import ContactFilters
from app.domain.common import Page
from app.domain.contacts import service
from app.domain.contacts.schemas import (
    ContactCreate,
    ContactProfileRead,
    ContactRead,
    ContactSort,
    ContactUpdate,
    ShareRequest,
    TimelineEntry,
)

router = APIRouter(prefix="/contacts", tags=["contacts"])
Member = Annotated[WorkspaceContext, Depends(require_role("member"))]


@router.get("", operation_id="contacts_list", response_model=Page[ContactRead])
async def contacts_list(
    ctx: CurrentUser,
    ws: Workspace,
    session: Session,
    q: Annotated[str | None, Query(max_length=120)] = None,
    status: Annotated[str | None, Query()] = None,
    band: Annotated[str | None, Query(pattern="^(strong|steady|weak|drifting)$")] = None,
    company_id: Annotated[UUID | None, Query()] = None,
    relationship_type: Annotated[str | None, Query()] = None,
    tag: Annotated[str | None, Query(max_length=60)] = None,
    owner: Annotated[str | None, Query(pattern="^me$")] = None,
    sort: ContactSort = "updated",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query()] = None,
) -> Page[ContactRead]:
    f = ContactFilters(
        q=q,
        status=status,
        band=band,
        company_id=company_id,
        relationship_type=relationship_type,
        tag=tag,
        owner_user_id=UUID(ctx.user_id) if owner == "me" else None,
    )
    return await service.list_contacts(session, ws, f, sort, limit, cursor)


@router.post("", operation_id="contacts_create", response_model=ContactRead, status_code=201)
async def contacts_create(body: ContactCreate, ctx: CurrentUser, ws: Member, session: Session) -> ContactRead:
    return await service.create_contact(session, ws, UUID(ctx.user_id), body)


@router.get("/{contact_id}", operation_id="contacts_get", response_model=ContactRead)
async def contacts_get(contact_id: UUID, ws: Workspace, session: Session) -> ContactRead:
    return await service.get_contact(session, ws, contact_id)


@router.patch("/{contact_id}", operation_id="contacts_update", response_model=ContactRead)
async def contacts_update(
    contact_id: UUID, body: ContactUpdate, ctx: CurrentUser, ws: Member, session: Session
) -> ContactRead:
    return await service.update_contact(session, ws, UUID(ctx.user_id), contact_id, body)


@router.delete("/{contact_id}", operation_id="contacts_delete", status_code=204)
async def contacts_delete(contact_id: UUID, ctx: CurrentUser, ws: Member, session: Session) -> Response:
    await service.delete_contact(session, ws, UUID(ctx.user_id), contact_id)
    return Response(status_code=204)


@router.post("/{contact_id}/share", operation_id="contacts_share", response_model=ContactRead, status_code=201)
async def contacts_share(
    contact_id: UUID, body: ShareRequest, ctx: CurrentUser, ws: Member, session: Session
) -> ContactRead:
    return await service.share_to_organization(session, ws, UUID(ctx.user_id), contact_id, body.target_workspace_id)


@router.post(
    "/{contact_id}/copy-to-personal",
    operation_id="contacts_copy_to_personal",
    response_model=ContactRead,
    status_code=201,
)
async def contacts_copy_to_personal(contact_id: UUID, ctx: CurrentUser, ws: Member, session: Session) -> ContactRead:
    return await service.copy_to_personal(session, ws, UUID(ctx.user_id), contact_id)


@router.get("/{contact_id}/timeline", operation_id="contacts_timeline", response_model=Page[TimelineEntry])
async def contacts_timeline(
    contact_id: UUID,
    ws: Workspace,
    session: Session,
    kinds: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query()] = None,
) -> Page[TimelineEntry]:
    return await service.timeline(session, ws, contact_id, kinds, limit, cursor)


@router.get("/{contact_id}/profile", operation_id="profile_get", response_model=ContactProfileRead)
async def profile_get(contact_id: UUID, ws: Workspace, session: Session) -> ContactProfileRead:
    return await service.get_profile(session, ws, contact_id)
