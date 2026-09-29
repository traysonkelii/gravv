from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import text

from app.auth.deps import CurrentUser, Session, Workspace, WorkspaceContext, require_role
from app.db.repositories.contacts import ContactFilters
from app.domain.captures.schemas import JobAccepted
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
from app.domain.insights.schemas import ScorePoint
from app.jobs import queue

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
async def contacts_update(contact_id: UUID, body: ContactUpdate, ctx: CurrentUser, ws: Member, session: Session) -> ContactRead:
    return await service.update_contact(session, ws, UUID(ctx.user_id), contact_id, body)


@router.delete("/{contact_id}", operation_id="contacts_delete", status_code=204)
async def contacts_delete(contact_id: UUID, ctx: CurrentUser, ws: Member, session: Session) -> Response:
    await service.delete_contact(session, ws, UUID(ctx.user_id), contact_id)
    return Response(status_code=204)


@router.post("/{contact_id}/share", operation_id="contacts_share", response_model=ContactRead, status_code=201)
async def contacts_share(contact_id: UUID, body: ShareRequest, ctx: CurrentUser, ws: Member, session: Session) -> ContactRead:
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


@router.post("/{contact_id}/profile/regenerate", operation_id="profile_regenerate", response_model=JobAccepted, status_code=202)
async def profile_regenerate(contact_id: UUID, ws: Member, session: Session) -> JobAccepted:
    await service.get_profile(session, ws, contact_id)
    job_id = await queue.enqueue(
        session,
        "profile.synthesize",
        {"contact_id": str(contact_id)},
        ws.workspace_id,
        priority=2,
        dedupe_key=f"profile.synthesize:{contact_id}",
    )
    return JobAccepted(job_id=job_id, deduplicated=job_id is None)


@router.get("/{contact_id}/scores", operation_id="scores_history", response_model=list[ScorePoint])
async def scores_history(
    contact_id: UUID, ws: Workspace, session: Session, range: Annotated[str, Query(pattern="^(30d|90d|1y)$")] = "90d"
) -> list[ScorePoint]:
    await service.get_profile(session, ws, contact_id)
    days = {"30d": 30, "90d": 90, "1y": 365}[range]
    rows = (
        await session.execute(
            text(
                "select scored_on::text, score, band from relationship_scores where contact_id = :id "
                "and scored_on >= current_date - cast(:days as int) order by scored_on"
            ),
            {"id": contact_id, "days": days},
        )
    ).all()
    return [ScorePoint(scored_on=r[0], score=r[1], band=r[2]) for r in rows]


@router.post("/{contact_id}/brief", operation_id="brief_create", response_model=JobAccepted, status_code=202)
async def brief_create(contact_id: UUID, ws: Member, session: Session) -> JobAccepted:
    await service.get_profile(session, ws, contact_id)
    job_id = await queue.enqueue(
        session,
        "brief.generate",
        {"contact_id": str(contact_id)},
        ws.workspace_id,
        priority=2,
        dedupe_key=f"brief.generate:{contact_id}",
    )
    return JobAccepted(job_id=job_id, deduplicated=job_id is None)
