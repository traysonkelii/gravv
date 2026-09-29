"""Contact reads go through the contact_overview view (RLS via security_invoker); writes through the ORM."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Contact, ContactProfile
from app.scoring.bands import BAND_SQL


@dataclass(frozen=True)
class ContactFilters:
    q: str | None = None
    status: str | None = None
    band: str | None = None
    company_id: UUID | None = None
    relationship_type: str | None = None
    tag: str | None = None
    owner_user_id: UUID | None = None
    ids: list[UUID] | None = None


# sort key -> (order by, cursor comparison operator, cursor value expression)
SORTS: dict[str, tuple[str, str, str]] = {
    "updated": ("updated_at desc, id desc", "<", "updated_at"),
    "gravity": ("gravity_score desc, id desc", "<", "gravity_score"),
    "last_interaction": (
        "coalesce(last_interaction_at, 'epoch'::timestamptz) desc, id desc",
        "<",
        "coalesce(last_interaction_at, 'epoch'::timestamptz)",
    ),
    "name": ("display_name asc, id asc", ">", "display_name"),
    "next_due": (
        "coalesce(next_due_at, '9999-12-31'::timestamptz) asc, id asc",
        ">",
        "coalesce(next_due_at, '9999-12-31'::timestamptz)",
    ),
}
CURSOR_CAST = {
    "updated": "timestamptz",
    "gravity": "int",
    "last_interaction": "timestamptz",
    "name": "text",
    "next_due": "timestamptz",
}

_BASE = f"""
with base as (
  select o.*, {BAND_SQL.format(t="o")} as band,
         li.id as li_id, li.kind::text as li_kind, li.occurred_at as li_occurred_at, li.summary as li_summary,
         li.subject as li_subject
  from contact_overview o
  left join lateral (
    select i.id, i.kind, i.occurred_at, i.summary, i.subject from interactions i
    where i.contact_id = o.id and i.deleted_at is null order by i.occurred_at desc limit 1
  ) li on true
  where o.workspace_id = :ws
)
"""


def _filters(f: ContactFilters, params: dict[str, Any]) -> str:
    clauses = []
    if f.status:
        clauses.append("status = cast(:status as contact_status)")
        params["status"] = f.status
    if f.band:
        clauses.append("band = :band")
        params["band"] = f.band
    if f.company_id:
        clauses.append("company_id = :company_id")
        params["company_id"] = f.company_id
    if f.relationship_type:
        clauses.append("relationship_type = cast(:rel as relationship_type)")
        params["rel"] = f.relationship_type
    if f.tag:
        clauses.append(":tag = any(tags)")
        params["tag"] = f.tag
    if f.owner_user_id:
        clauses.append("owner_user_id = :owner")
        params["owner"] = f.owner_user_id
    if f.ids is not None:
        clauses.append("id = any(cast(:ids as uuid[]))")
        params["ids"] = f.ids
    if f.q:
        clauses.append("id in (select id from search_contacts(:ws, :q, 200))")
        params["q"] = f.q
    return (" and " + " and ".join(clauses)) if clauses else ""


async def list_overview(
    session: AsyncSession, ws: UUID, f: ContactFilters, sort: str, limit: int, after: list[Any] | None
) -> list[RowMapping]:
    order_by, op, expr = SORTS[sort]
    params: dict[str, Any] = {"ws": ws, "lim": limit + 1}
    where = _filters(f, params)
    if after:
        where += f" and ({expr}, id) {op} (cast(:cv as {CURSOR_CAST[sort]}), cast(:cid as uuid))"
        params["cv"], params["cid"] = after[0], after[1]
    sql = f"{_BASE} select * from base where true {where} order by {order_by} limit :lim"
    return list((await session.execute(text(sql), params)).mappings().all())


async def get_overview(session: AsyncSession, ws: UUID, contact_id: UUID) -> RowMapping | None:
    sql = f"{_BASE} select * from base where id = :id"
    return (await session.execute(text(sql), {"ws": ws, "id": contact_id})).mappings().first()


def cursor_value(row: RowMapping, sort: str) -> Any:
    if sort == "gravity":
        return row["gravity_score"]
    if sort == "name":
        return row["display_name"]
    if sort == "last_interaction":
        return row["last_interaction_at"] or "1970-01-01T00:00:00+00:00"
    if sort == "next_due":
        return row["next_due_at"] or "9999-12-31T00:00:00+00:00"
    return row["updated_at"]


async def get_contact(session: AsyncSession, ws: UUID, contact_id: UUID) -> Contact | None:
    return await session.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == ws, Contact.deleted_at.is_(None))
    )


async def create_contact(session: AsyncSession, fields: dict[str, Any]) -> Contact:
    contact = Contact(**fields)
    session.add(contact)
    await session.flush()
    await session.refresh(contact)
    return contact


async def update_contact(session: AsyncSession, contact: Contact, fields: dict[str, Any]) -> Contact:
    for k, v in fields.items():
        setattr(contact, k, v)
    await session.flush()
    await session.refresh(contact)
    return contact


async def soft_delete_contact(session: AsyncSession, contact: Contact) -> None:
    # Core update without RETURNING: a returned row would have to pass the select policy (deleted_at is null).
    await session.execute(update(Contact).where(Contact.id == contact.id).values(deleted_at=func.now()))


async def get_profile(session: AsyncSession, contact_id: UUID) -> ContactProfile | None:
    return await session.get(ContactProfile, contact_id)


_TIMELINE = """
with entries as (
  select 'interaction' as entry_type, i.id, i.occurred_at as ts, i.kind::text as kind,
         coalesce(nullif(i.subject, ''), initcap(i.kind::text)) as title,
         coalesce(nullif(i.summary, ''), left(i.body, 240)) as body,
         jsonb_build_object('sentiment', i.sentiment, 'user_id', i.user_id, 'direction', i.direction,
                            'source', i.source, 'ai_status', i.ai_status) as meta
  from interactions i where i.contact_id = :cid and i.deleted_at is null
  union all
  select 'task', t.id, t.completed_at, 'task', t.title, coalesce(t.description, ''),
         jsonb_build_object('status', t.status, 'assignee_user_id', t.assignee_user_id)
  from tasks t where t.contact_id = :cid and t.status = 'done' and t.completed_at is not null
  union all
  select 'score', x.id, (x.scored_on::timestamp at time zone 'UTC') + interval '12 hours', 'score',
         'Gravity ' || x.score, x.band, jsonb_build_object('score', x.score, 'band', x.band, 'previous', x.prev)
  from (select rs.*, lag(rs.score) over (partition by rs.contact_id order by rs.scored_on) as prev
        from relationship_scores rs where rs.contact_id = :cid) x
  where x.prev is null or x.prev <> x.score
)
select * from entries
where (cast(:kinds as text[]) is null or kind = any(cast(:kinds as text[])))
  and (cast(:cts as timestamptz) is null or (ts, id) < (cast(:cts as timestamptz), cast(:cid2 as uuid)))
order by ts desc, id desc limit :lim
"""


async def timeline(
    session: AsyncSession, contact_id: UUID, kinds: list[str] | None, limit: int, after: list[Any] | None
) -> list[RowMapping]:
    params: dict[str, Any] = {
        "cid": contact_id,
        "kinds": kinds,
        "lim": limit + 1,
        "cts": after[0] if after else None,
        "cid2": after[1] if after else None,
    }
    return list((await session.execute(text(_TIMELINE), params)).mappings().all())
