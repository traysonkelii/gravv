from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import WorkspaceContext
from app.domain.analytics.schemas import AnalyticsSummary, BandCount, MemberMetrics, SeriesPoint, TopContact
from app.errors import Problem
from app.scoring.bands import BAND_SQL

RANGE_DAYS = {"today": 1, "week": 7, "month": 30, "quarter": 90, "year": 365}
BUCKET = {"today": "hour", "week": "day", "month": "day", "quarter": "week", "year": "month"}


def _scope(ws: WorkspaceContext, scope: str, user_id: UUID, params: dict[str, Any]) -> str:
    if scope == "team":
        if not ws.at_least("manager"):
            raise Problem(403, "insufficient_role", "Insufficient role", "Team analytics require the manager role.")
        return ""
    params["uid"] = user_id
    return " and c.owner_user_id = :uid"


async def summary(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, range_: str, scope: str) -> AnalyticsSummary:
    days = RANGE_DAYS[range_]
    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    prev_since = since - timedelta(days=days)
    params: dict[str, Any] = {
        "ws": ws.workspace_id,
        "since": since,
        "prev_since": prev_since,
        "since_date": since.date(),
    }
    owner = _scope(ws, scope, user_id, params)
    row = (
        (
            await session.execute(
                text(f"""
        with base as (select c.* from contacts c where c.workspace_id = :ws and c.deleted_at is null and c.status <> 'archived'{owner})
        select
          (select count(*) from base) as contact_count,
          (select count(*) from base where created_at >= :since) - (select count(*) from base where created_at >= :prev_since and created_at < :since) as contact_delta,
          (select count(*) from base b where exists (select 1 from interactions i where i.contact_id = b.id and i.deleted_at is null and i.occurred_at >= :since)) as active_count,
          (select coalesce(round(avg(gravity_score)), 0) from base) as avg_gravity,
          (select coalesce(round(avg(rs.score)), 0) from base b join lateral (
              select score from relationship_scores rs where rs.contact_id = b.id and rs.scored_on <= :since_date order by scored_on desc limit 1) rs on true) as avg_gravity_then,
          (select count(*) from base where next_due_at <= now() + interval '7 days') as due_count
        """),
                params,
            )
        )
        .mappings()
        .one()
    )
    opp_owner = " and o.owner_user_id = :uid" if scope != "team" else ""
    opp = (
        (
            await session.execute(
                text(f"""
        select coalesce(sum(o.value_cents) filter (where o.status = 'open'), 0) as pipeline,
               count(*) filter (where o.status = 'open') as open_count,
               coalesce(sum(o.value_cents) filter (where o.status = 'open' and o.created_at < :since), 0) as pipeline_then
        from opportunities o where o.workspace_id = :ws and o.deleted_at is null{opp_owner}
        """),
                params,
            )
        )
        .mappings()
        .one()
    )
    then = int(opp["pipeline_then"])
    pipeline = int(opp["pipeline"])
    contact_count = int(row["contact_count"])
    return AnalyticsSummary(
        range=range_,
        scope=scope,
        contact_count=contact_count,
        contact_count_delta=int(row["contact_delta"]),
        active_count=int(row["active_count"]),
        engagement_rate=round(int(row["active_count"]) / contact_count, 3) if contact_count else 0.0,
        avg_gravity=int(row["avg_gravity"]),
        avg_gravity_delta=int(row["avg_gravity"]) - int(row["avg_gravity_then"]) if int(row["avg_gravity_then"]) else 0,
        pipeline_value_cents=pipeline,
        pipeline_delta_pct=round((pipeline - then) / then * 100, 1) if then else 0.0,
        open_opportunity_count=int(opp["open_count"]),
        due_count=int(row["due_count"]),
    )


async def distribution(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, scope: str) -> list[BandCount]:
    params: dict[str, Any] = {"ws": ws.workspace_id}
    owner = _scope(ws, scope, user_id, params)
    band = BAND_SQL.format(t="c")
    rows = (
        await session.execute(
            text(f"""
        select band, count(*) as n from (select {band} as band from contacts c
          where c.workspace_id = :ws and c.deleted_at is null and c.status <> 'archived'{owner}) x group by band
        """),
            params,
        )
    ).all()
    counts = {r[0]: int(r[1]) for r in rows}
    return [BandCount(band=b, count=counts.get(b, 0)) for b in ("strong", "steady", "weak", "drifting")]


async def interactions_series(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, range_: str, scope: str) -> list[SeriesPoint]:
    days = RANGE_DAYS[range_]
    params: dict[str, Any] = {"ws": ws.workspace_id, "since": datetime.now(UTC) - timedelta(days=days)}
    owner = " and i.user_id = :uid" if scope != "team" else ""
    if scope == "team" and not ws.at_least("manager"):
        raise Problem(403, "insufficient_role", "Insufficient role", "Team analytics require the manager role.")
    if scope != "team":
        params["uid"] = user_id
    bucket = BUCKET[range_]
    rows = (
        await session.execute(
            text(f"""
        select to_char(date_trunc('{bucket}', i.occurred_at), 'YYYY-MM-DD"T"HH24:MI') as period, i.kind::text, count(*)
        from interactions i where i.workspace_id = :ws and i.deleted_at is null and i.occurred_at >= :since{owner}
        group by 1, 2 order by 1, 2
        """),
            params,
        )
    ).all()
    return [SeriesPoint(period=r[0], kind=r[1], count=int(r[2])) for r in rows]


async def top_contacts(
    session: AsyncSession, ws: WorkspaceContext, user_id: UUID, scope: str, q: str | None, limit: int
) -> list[TopContact]:
    params: dict[str, Any] = {"ws": ws.workspace_id, "lim": limit}
    owner = _scope(ws, scope, user_id, params)
    search = ""
    if q:
        search = " and (c.display_name ilike '%' || :q || '%' or co.name ilike '%' || :q || '%')"
        params["q"] = q
    band = BAND_SQL.format(t="c")
    rows = (
        (
            await session.execute(
                text(f"""
        select c.id, c.display_name, c.honorific, co.name as company_name, c.gravity_score, {band} as band, c.status::text,
               c.last_interaction_at,
               (select coalesce(sum(o.value_cents), 0) from opportunity_contacts oc join opportunities o on o.id = oc.opportunity_id
                  where oc.contact_id = c.id and o.status = 'open' and o.deleted_at is null) as deal_value
        from contacts c left join companies co on co.id = c.company_id
        where c.workspace_id = :ws and c.deleted_at is null and c.status <> 'archived'{owner}{search}
        order by c.gravity_score desc, c.last_interaction_at desc nulls last limit :lim
        """),
                params,
            )
        )
        .mappings()
        .all()
    )
    return [
        TopContact(
            id=r["id"],
            display_name=r["display_name"],
            honorific=r["honorific"],
            company_name=r["company_name"],
            gravity_score=r["gravity_score"],
            band=r["band"],
            status=r["status"],
            last_interaction_at=r["last_interaction_at"].isoformat() if r["last_interaction_at"] else None,
            deal_value_cents=int(r["deal_value"]),
        )
        for r in rows
    ]


async def team(session: AsyncSession, ws: WorkspaceContext, range_: str) -> list[MemberMetrics]:
    if not ws.at_least("manager"):
        raise Problem(403, "insufficient_role", "Insufficient role", "Team analytics require the manager role.")
    since = datetime.now(UTC) - timedelta(days=RANGE_DAYS[range_])
    rows = (
        (
            await session.execute(
                text("""
        select m.user_id, m.full_name, m.role::text,
          (select count(*) from contacts c where c.workspace_id = :ws and c.owner_user_id = m.user_id and c.deleted_at is null and c.status <> 'archived') as contacts,
          (select coalesce(round(avg(c.gravity_score)), 0) from contacts c where c.workspace_id = :ws and c.owner_user_id = m.user_id and c.deleted_at is null and c.status <> 'archived') as avg_gravity,
          (select count(*) from interactions i where i.workspace_id = :ws and i.user_id = m.user_id and i.deleted_at is null and i.occurred_at >= :since) as interactions,
          (select coalesce(sum(o.value_cents), 0) from opportunities o where o.workspace_id = :ws and o.owner_user_id = m.user_id and o.status = 'open' and o.deleted_at is null) as pipeline,
          (select count(*) from tasks t where t.workspace_id = :ws and t.assignee_user_id = m.user_id and t.status = 'open' and t.due_at < now()) as overdue
        from member_directory m where m.workspace_id = :ws and m.status = 'active' order by m.full_name
        """),
                {"ws": ws.workspace_id, "since": since},
            )
        )
        .mappings()
        .all()
    )
    return [
        MemberMetrics(
            user_id=r["user_id"],
            full_name=r["full_name"],
            role=r["role"],
            contact_count=int(r["contacts"]),
            avg_gravity=int(r["avg_gravity"]),
            interactions_in_range=int(r["interactions"]),
            pipeline_value_cents=int(r["pipeline"]),
            overdue_tasks=int(r["overdue"]),
        )
        for r in rows
    ]
