from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import WorkspaceContext
from app.db.repositories import companies as companies_repo
from app.db.repositories import contacts as contacts_repo
from app.domain.audit import write_audit
from app.domain.common import Page, decode_cursor, encode_cursor, page_of
from app.domain.companies.schemas import CompanySummary
from app.domain.opportunities.schemas import (
    OpportunityContactRead,
    OpportunityCreate,
    OpportunityRead,
    OpportunityUpdate,
)
from app.errors import Problem
from app.scoring.compute import rescore_contact

_SELECT = """
select o.id, o.workspace_id, o.owner_user_id, o.name, o.value_cents, o.currency, o.stage, o.probability, o.expected_close,
       o.status::text, o.notes, o.created_at, o.updated_at, co.id as company_id, co.name as company_name, co.industry
from opportunities o left join companies co on co.id = o.company_id
"""
_CONTACTS = text("""
select oc.contact_id, c.display_name, c.honorific, oc.role::text, c.gravity_score
from opportunity_contacts oc join contacts c on c.id = oc.contact_id where oc.opportunity_id = :id and c.deleted_at is null
order by c.gravity_score desc
""")


async def _read(session: AsyncSession, r: Any) -> OpportunityRead:
    contacts = [
        OpportunityContactRead(contact_id=x[0], display_name=x[1], honorific=x[2], role=x[3], gravity_score=x[4])
        for x in (await session.execute(_CONTACTS, {"id": r["id"]})).all()
    ]
    company = CompanySummary(id=r["company_id"], name=r["company_name"], industry=r["industry"]) if r["company_id"] else None
    return OpportunityRead(
        id=r["id"],
        workspace_id=r["workspace_id"],
        owner_user_id=r["owner_user_id"],
        company=company,
        name=r["name"],
        value_cents=r["value_cents"],
        currency=r["currency"],
        stage=r["stage"],
        probability=r["probability"],
        expected_close=r["expected_close"],
        status=r["status"],
        notes=r["notes"],
        contacts=contacts,
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


async def _get_row(session: AsyncSession, ws: WorkspaceContext, opp_id: UUID) -> Any:
    r = (
        (
            await session.execute(
                text(f"{_SELECT} where o.id = :id and o.workspace_id = :ws and o.deleted_at is null"), {"id": opp_id, "ws": ws.workspace_id}
            )
        )
        .mappings()
        .first()
    )
    if r is None:
        raise Problem(404, "not_found", "Opportunity not found")
    return r


async def get(session: AsyncSession, ws: WorkspaceContext, opp_id: UUID) -> OpportunityRead:
    return await _read(session, await _get_row(session, ws, opp_id))


async def list_opportunities(
    session: AsyncSession,
    ws: WorkspaceContext,
    user_id: UUID,
    status: str | None,
    company_id: UUID | None,
    owner_me: bool,
    limit: int,
    cursor: str | None,
) -> Page[OpportunityRead]:
    params: dict[str, Any] = {"ws": ws.workspace_id, "lim": limit + 1}
    where = ["o.workspace_id = :ws", "o.deleted_at is null"]
    if status:
        where.append("o.status = cast(:status as opportunity_status)")
        params["status"] = status
    if company_id:
        where.append("o.company_id = :company_id")
        params["company_id"] = company_id
    if owner_me:
        where.append("o.owner_user_id = :uid")
        params["uid"] = user_id
    after = decode_cursor(cursor)
    if after:
        where.append("(o.updated_at, o.id) < (cast(:cu as timestamptz), cast(:cid as uuid))")
        params["cu"], params["cid"] = after[0], after[1]
    rows = (
        (await session.execute(text(f"{_SELECT} where {' and '.join(where)} order by o.updated_at desc, o.id desc limit :lim"), params))
        .mappings()
        .all()
    )
    items, next_cursor = page_of(list(rows), limit, lambda r: encode_cursor(r["updated_at"].isoformat(), r["id"]))
    return Page(items=[await _read(session, r) for r in items], next_cursor=next_cursor)


async def _company(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, company_id: UUID | None, name: str | None) -> UUID | None:
    if company_id:
        if await companies_repo.get_company(session, ws.workspace_id, company_id) is None:
            raise Problem(422, "invalid_reference", "Invalid reference", "That company does not exist here.")
        return company_id
    if name and name.strip():
        return (await companies_repo.find_or_create(session, ws.workspace_id, user_id, name)).id
    return None


async def create(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, body: OpportunityCreate) -> OpportunityRead:
    company_id = await _company(session, ws, user_id, body.company_id, body.company_name)
    opp_id = await session.scalar(
        text(
            "insert into opportunities (workspace_id, company_id, owner_user_id, name, value_cents, currency, stage, probability, "
            "expected_close, status, notes) values (:ws, :co, :u, :name, :value, :cur, :stage, :prob, :close, "
            "cast(:status as opportunity_status), :notes) returning id"
        ),
        {
            "ws": ws.workspace_id,
            "co": company_id,
            "u": user_id,
            "name": body.name,
            "value": body.value_cents,
            "cur": body.currency.upper(),
            "stage": body.stage,
            "prob": body.probability,
            "close": body.expected_close,
            "status": body.status.value,
            "notes": body.notes,
        },
    )
    assert opp_id is not None
    await write_audit(session, ws.workspace_id, "opportunity.create", "opportunity", opp_id, {"name": body.name})
    return await get(session, ws, opp_id)


async def update(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, opp_id: UUID, body: OpportunityUpdate) -> OpportunityRead:
    row = await _get_row(session, ws, opp_id)
    if row["owner_user_id"] != user_id and not ws.at_least("manager"):
        raise Problem(403, "insufficient_role", "Insufficient role", "Editing another person's deal requires the manager role.")
    fields = body.model_dump(exclude_unset=True, exclude={"company_id", "company_name"})
    if "company_id" in body.model_fields_set or "company_name" in body.model_fields_set:
        fields["company_id"] = await _company(session, ws, user_id, body.company_id, body.company_name)
    if "status" in fields and fields["status"] is not None:
        fields["status"] = fields["status"].value
    if fields.get("currency"):
        fields["currency"] = fields["currency"].upper()
    if fields:
        sets = ", ".join("status = cast(:status as opportunity_status)" if k == "status" else f"{k} = :{k}" for k in fields)
        await session.execute(text(f"update opportunities set {sets} where id = :id"), {**fields, "id": opp_id})
        for (cid,) in (
            await session.execute(text("select contact_id from opportunity_contacts where opportunity_id = :id"), {"id": opp_id})
        ).all():
            await rescore_contact(session, cid)
        await write_audit(session, ws.workspace_id, "opportunity.update", "opportunity", opp_id, fields)
    return await get(session, ws, opp_id)


async def delete(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, opp_id: UUID) -> None:
    row = await _get_row(session, ws, opp_id)
    if row["owner_user_id"] != user_id and not ws.at_least("admin"):
        raise Problem(403, "insufficient_role", "Insufficient role", "Deleting another person's deal requires the admin role.")
    await session.execute(text("update opportunities set deleted_at = now() where id = :id"), {"id": opp_id})
    await write_audit(session, ws.workspace_id, "opportunity.delete", "opportunity", opp_id)


async def put_contact(session: AsyncSession, ws: WorkspaceContext, opp_id: UUID, contact_id: UUID, role: str) -> OpportunityRead:
    await _get_row(session, ws, opp_id)
    if await contacts_repo.get_contact(session, ws.workspace_id, contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")
    await session.execute(
        text(
            "insert into opportunity_contacts (opportunity_id, contact_id, role) values (:o, :c, cast(:r as opportunity_role)) "
            "on conflict (opportunity_id, contact_id) do update set role = excluded.role"
        ),
        {"o": opp_id, "c": contact_id, "r": role},
    )
    await rescore_contact(session, contact_id)
    return await get(session, ws, opp_id)


async def delete_contact(session: AsyncSession, ws: WorkspaceContext, opp_id: UUID, contact_id: UUID) -> OpportunityRead:
    await _get_row(session, ws, opp_id)
    await session.execute(
        text("delete from opportunity_contacts where opportunity_id = :o and contact_id = :c"), {"o": opp_id, "c": contact_id}
    )
    await rescore_contact(session, contact_id)
    return await get(session, ws, opp_id)
