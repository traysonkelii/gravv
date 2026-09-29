from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import WorkspaceContext
from app.db.enums import ContactVisibility, WorkspaceKind
from app.db.models import Contact
from app.db.repositories import companies as companies_repo
from app.db.repositories import contacts as repo
from app.db.repositories import facts as facts_repo
from app.db.repositories import interactions as interactions_repo
from app.db.repositories import workspaces as workspaces_repo
from app.domain.audit import write_audit
from app.domain.common import Page, decode_cursor, encode_cursor, page_of
from app.domain.companies.schemas import CompanySummary
from app.domain.contacts.schemas import (
    ContactCreate,
    ContactProfileRead,
    ContactRead,
    ContactUpdate,
    InteractionSummary,
    TimelineEntry,
)
from app.errors import Problem


def _read(row: RowMapping, profile: ContactProfileRead | None = None) -> ContactRead:
    company = None
    if row["company_id"] is not None and row["company_name"] is not None:
        company = CompanySummary(id=row["company_id"], name=row["company_name"], industry=row["company_industry"])
    last = None
    if row["li_id"] is not None:
        last = InteractionSummary(
            id=row["li_id"],
            kind=row["li_kind"],
            occurred_at=row["li_occurred_at"],
            summary=row["li_summary"],
            subject=row["li_subject"],
        )
    return ContactRead(
        id=row["id"],
        workspace_id=row["workspace_id"],
        owner_user_id=row["owner_user_id"],
        display_name=row["display_name"],
        honorific=row["honorific"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        title=row["title"],
        company=company,
        emails=list(row["emails"] or []),
        phones=list(row["phones"] or []),
        location=row["location"],
        relationship_type=row["relationship_type"],
        visibility=row["visibility"],
        status=row["status"],
        tags=list(row["tags"] or []),
        cadence_days=row["cadence_days"],
        gravity_score=row["gravity_score"],
        band=row["band"],
        score_delta_30d=row["score_delta_30d"],
        last_interaction=last,
        next_due_at=row["next_due_at"],
        open_task_count=row["open_task_count"],
        open_opportunity_value_cents=row["open_opportunity_value_cents"],
        origin_contact_id=row["origin_contact_id"],
        profile=profile,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def list_contacts(
    session: AsyncSession, ws: WorkspaceContext, f: repo.ContactFilters, sort: str, limit: int, cursor: str | None
) -> Page[ContactRead]:
    after = decode_cursor(cursor)
    if after and after[0] != sort:
        raise Problem(400, "bad_cursor", "Invalid cursor", "The cursor belongs to a different sort order.")
    rows = await repo.list_overview(session, ws.workspace_id, f, sort, limit, after[1:] if after else None)
    items, next_cursor = page_of(rows, limit, lambda r: encode_cursor(sort, repo.cursor_value(r, sort), r["id"]))
    return Page(items=[_read(r) for r in items], next_cursor=next_cursor)


async def get_contact(session: AsyncSession, ws: WorkspaceContext, contact_id: UUID) -> ContactRead:
    row = await repo.get_overview(session, ws.workspace_id, contact_id)
    if row is None:
        raise Problem(404, "not_found", "Contact not found")
    profile = await repo.get_profile(session, contact_id)
    return _read(row, ContactProfileRead.model_validate(profile) if profile else None)


async def _resolve_company(
    session: AsyncSession, ws: WorkspaceContext, user_id: UUID, company_id: UUID | None, company_name: str | None
) -> UUID | None:
    if company_id is not None:
        company = await companies_repo.get_company(session, ws.workspace_id, company_id)
        if company is None:
            raise Problem(422, "invalid_reference", "Invalid reference", "That company does not exist here.")
        return company.id
    if company_name and company_name.strip():
        return (await companies_repo.find_or_create(session, ws.workspace_id, user_id, company_name)).id
    return None


async def create_contact(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, body: ContactCreate) -> ContactRead:
    fields: dict[str, Any] = body.model_dump(exclude={"company_id", "company_name", "visibility"})
    fields["company_id"] = await _resolve_company(session, ws, user_id, body.company_id, body.company_name)
    fields["visibility"] = body.visibility or ContactVisibility(ws.settings.get("default_contact_visibility", "team"))
    if body.cadence_days == 30 and "default_cadence_days" in ws.settings:
        fields["cadence_days"] = int(ws.settings["default_cadence_days"])
    fields.update(workspace_id=ws.workspace_id, owner_user_id=user_id)
    contact = await repo.create_contact(session, fields)
    await write_audit(session, ws.workspace_id, "contact.create", "contact", contact.id, {"display_name": contact.display_name})
    return await get_contact(session, ws, contact.id)


async def _load_for_write(
    session: AsyncSession, ws: WorkspaceContext, user_id: UUID, contact_id: UUID, min_role_for_others: str
) -> Contact:
    contact = await repo.get_contact(session, ws.workspace_id, contact_id)
    if contact is None:
        raise Problem(404, "not_found", "Contact not found")
    if contact.owner_user_id != user_id and not ws.at_least(min_role_for_others):
        raise Problem(
            403,
            "insufficient_role",
            "Insufficient role",
            f"Editing a contact owned by someone else requires the {min_role_for_others} role.",
        )
    return contact


async def update_contact(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, contact_id: UUID, body: ContactUpdate) -> ContactRead:
    contact = await _load_for_write(session, ws, user_id, contact_id, "manager")
    fields = body.model_dump(exclude_unset=True, exclude={"company_id", "company_name"})
    if "company_id" in body.model_fields_set or "company_name" in body.model_fields_set:
        fields["company_id"] = await _resolve_company(session, ws, user_id, body.company_id, body.company_name)
    await repo.update_contact(session, contact, fields)
    await write_audit(session, ws.workspace_id, "contact.update", "contact", contact.id, fields)
    return await get_contact(session, ws, contact_id)


async def delete_contact(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, contact_id: UUID) -> None:
    contact = await _load_for_write(session, ws, user_id, contact_id, "admin")
    await repo.soft_delete_contact(session, contact)
    await write_audit(session, ws.workspace_id, "contact.delete", "contact", contact.id)


async def _copy_contact(
    session: AsyncSession,
    source: Contact,
    source_ws: UUID,
    target_ws: UUID,
    user_id: UUID,
    visibility: ContactVisibility,
) -> Contact:
    company_id = None
    if source.company_id is not None:
        company = await companies_repo.get_company(session, source_ws, source.company_id)
        if company is not None:
            company_id = (await companies_repo.find_or_create(session, target_ws, user_id, company.name)).id
    copy = await repo.create_contact(
        session,
        {
            "workspace_id": target_ws,
            "owner_user_id": user_id,
            "company_id": company_id,
            "first_name": source.first_name,
            "last_name": source.last_name,
            "honorific": source.honorific,
            "title": source.title,
            "emails": list(source.emails),
            "phones": list(source.phones),
            "location": source.location,
            "relationship_type": source.relationship_type,
            "visibility": visibility,
            "tags": list(source.tags),
            "cadence_days": source.cadence_days,
            "origin_contact_id": source.id,
            "source": "copy",
        },
    )
    for fact in await facts_repo.list_facts(session, source.id, include_inactive=False):
        await facts_repo.create_fact(
            session,
            {
                "workspace_id": target_ws,
                "contact_id": copy.id,
                "category": fact.category,
                "content": fact.content,
                "confidence": fact.confidence,
                "source": fact.source,
                "created_by": user_id,
            },
        )
    for i in await interactions_repo.list_for_contact(session, source.id, limit=500):
        if i.user_id != user_id:
            continue
        await interactions_repo.create_interaction(
            session,
            {
                "workspace_id": target_ws,
                "contact_id": copy.id,
                "user_id": user_id,
                "kind": i.kind,
                "direction": i.direction,
                "occurred_at": i.occurred_at,
                "subject": i.subject,
                "body": i.body,
                "summary": i.summary,
                "sentiment": i.sentiment,
                "sentiment_score": i.sentiment_score,
                "source": i.source,
                "metadata_": {"copied_from": str(i.id)},
            },
        )
    return copy


async def share_to_organization(
    session: AsyncSession, ws: WorkspaceContext, user_id: UUID, contact_id: UUID, target_workspace_id: UUID
) -> ContactRead:
    contact = await repo.get_contact(session, ws.workspace_id, contact_id)
    if contact is None:
        raise Problem(404, "not_found", "Contact not found")
    source_ws = await workspaces_repo.get_workspace(session, ws.workspace_id)
    target_ws = await workspaces_repo.get_workspace(session, target_workspace_id)
    if source_ws is None or source_ws.kind != WorkspaceKind.personal:
        raise Problem(422, "validation_error", "Invalid request", "Only personal contacts can be shared.")
    if target_ws is None or target_ws.kind != WorkspaceKind.organization:
        raise Problem(403, "not_a_member", "Not a member", "You are not a member of that organization.")
    membership = await workspaces_repo.get_membership(session, target_workspace_id, user_id)
    if membership is None or membership.status != "active" or membership.role == "viewer":
        raise Problem(403, "insufficient_role", "Insufficient role", "You cannot add contacts to that organization.")
    visibility = ContactVisibility(target_ws.settings.get("default_contact_visibility", "team"))
    copy = await _copy_contact(session, contact, ws.workspace_id, target_workspace_id, user_id, visibility)
    await write_audit(session, target_workspace_id, "contact.share", "contact", copy.id, {"origin": str(contact.id)})
    target_ctx = WorkspaceContext(workspace_id=target_workspace_id, role=membership.role, settings=target_ws.settings)
    return await get_contact(session, target_ctx, copy.id)


async def copy_to_personal(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, contact_id: UUID) -> ContactRead:
    contact = await repo.get_contact(session, ws.workspace_id, contact_id)
    if contact is None:
        raise Problem(404, "not_found", "Contact not found")
    if contact.owner_user_id != user_id:
        raise Problem(403, "forbidden", "Forbidden", "You can only copy contacts you created.")
    rows = await workspaces_repo.list_memberships(session, user_id)
    personal = next((w for _m, w in rows if w.kind == WorkspaceKind.personal), None)
    if personal is None or personal.id == ws.workspace_id:
        raise Problem(422, "validation_error", "Invalid request", "This contact is already in your personal workspace.")
    copy = await _copy_contact(session, contact, ws.workspace_id, personal.id, user_id, ContactVisibility.private)
    await write_audit(session, ws.workspace_id, "contact.copy_to_personal", "contact", contact.id, {"copy": str(copy.id)})
    personal_ctx = WorkspaceContext(workspace_id=personal.id, role="owner", settings=personal.settings)
    return await get_contact(session, personal_ctx, copy.id)


async def timeline(
    session: AsyncSession,
    ws: WorkspaceContext,
    contact_id: UUID,
    kinds: list[str] | None,
    limit: int,
    cursor: str | None,
) -> Page[TimelineEntry]:
    if await repo.get_contact(session, ws.workspace_id, contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")
    after = decode_cursor(cursor)
    rows = await repo.timeline(session, contact_id, kinds or None, limit, after)
    items, next_cursor = page_of(rows, limit, lambda r: encode_cursor(r["ts"].isoformat(), r["id"]))
    return Page(items=[TimelineEntry(**dict(r)) for r in items], next_cursor=next_cursor)


async def get_profile(session: AsyncSession, ws: WorkspaceContext, contact_id: UUID) -> ContactProfileRead:
    if await repo.get_contact(session, ws.workspace_id, contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")
    profile = await repo.get_profile(session, contact_id)
    if profile is None:
        raise Problem(404, "not_found", "Profile not found")
    return ContactProfileRead.model_validate(profile)


async def touch_last_interaction(session: AsyncSession, contact_id: UUID) -> None:
    """Recomputes contacts.last_interaction_at from the surviving interactions (after an edit or delete)."""
    await session.execute(
        text(
            "update contacts c set last_interaction_at = (select max(occurred_at) from interactions i "
            "where i.contact_id = c.id and i.deleted_at is null) where c.id = :id"
        ),
        {"id": contact_id},
    )
