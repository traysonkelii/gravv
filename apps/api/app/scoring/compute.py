"""Gathers score inputs with SQL and writes results through apply_score(). Runs under the caller's identity in
requests and as the worker in the nightly job."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.gravity import InteractionPoint, ScoreInputs, ScoreResult, compute

_INPUTS = text("""
select c.cadence_days, c.status::text, c.gravity_score,
  (select count(*) from contact_facts f where f.contact_id = c.id and f.is_active) as facts,
  exists (select 1 from contact_facts f where f.contact_id = c.id and f.is_active and f.category = 'communication_style')
    or exists (select 1 from contact_profiles p where p.contact_id = c.id and coalesce(p.communication_style, '') <> '') as style_known,
  (select count(*) from tasks t where t.contact_id = c.id and t.status = 'open' and t.due_at < now()) as overdue,
  (select count(*) from tasks t where t.contact_id = c.id and t.status = 'open' and t.due_at >= now()
     and t.due_at < now() + interval '3 days') as due_soon,
  (select min(t.due_at) from tasks t where t.contact_id = c.id and t.status = 'open') as earliest_due,
  (select count(*) from opportunity_contacts oc join opportunities o on o.id = oc.opportunity_id
     where oc.contact_id = c.id and o.status = 'open' and o.deleted_at is null) as opp_count,
  (select coalesce(sum(o.value_cents), 0) from opportunity_contacts oc join opportunities o on o.id = oc.opportunity_id
     where oc.contact_id = c.id and o.status = 'open' and o.deleted_at is null) as opp_value,
  (select rs.score from relationship_scores rs where rs.contact_id = c.id and rs.scored_on <= cast(:today as date) - 30
     order by rs.scored_on desc limit 1) as score_30d_ago,
  (select rs.score from relationship_scores rs where rs.contact_id = c.id and rs.scored_on < cast(:today as date)
     order by rs.scored_on desc limit 1) as previous_score
from contacts c where c.id = :id and c.deleted_at is null
""")
_POINTS = text("""
select occurred_at, direction::text, sentiment_score from interactions
where contact_id = :id and deleted_at is null and occurred_at >= :since order by occurred_at desc limit 500
""")


async def load_inputs(session: AsyncSession, contact_id: UUID, now: datetime) -> ScoreInputs | None:
    row = (await session.execute(_INPUTS, {"id": contact_id, "today": now.date()})).mappings().first()
    if row is None:
        return None
    since = now - timedelta(days=180)
    points = [InteractionPoint(r[0], r[1], r[2]) for r in (await session.execute(_POINTS, {"id": contact_id, "since": since})).all()]
    return ScoreInputs(
        cadence_days=row["cadence_days"],
        interactions=points,
        active_facts=int(row["facts"]),
        communication_style_known=bool(row["style_known"]),
        overdue_tasks=int(row["overdue"]),
        tasks_due_within_3_days=int(row["due_soon"]),
        earliest_open_task_due=row["earliest_due"],
        open_opportunity_count=int(row["opp_count"]),
        open_opportunity_value_cents=int(row["opp_value"]),
        score_30d_ago=row["score_30d_ago"],
        previous_score=row["previous_score"] if row["previous_score"] is not None else row["gravity_score"],
        archived=row["status"] == "archived",
    )


async def rescore_contact(session: AsyncSession, contact_id: UUID, now: datetime | None = None) -> ScoreResult | None:
    now = now or datetime.now(UTC)
    inputs = await load_inputs(session, contact_id, now)
    if inputs is None:
        return None
    result = compute(inputs, now)
    components: dict[str, Any] = {
        **result.components,
        "days_since_last": result.days_since_last,
        "delta_30d": result.delta_30d,
    }
    await session.execute(
        text(
            "select apply_score(:id, cast(:score as smallint), :band, cast(:status as contact_status), :due, "
            "cast(:components as jsonb), cast(:today as date))"
        ),
        {
            "id": contact_id,
            "score": result.score,
            "band": result.band.value,
            "status": result.status.value,
            "due": result.next_due_at,
            "components": json.dumps(components),
            "today": now.date(),
        },
    )
    return result


async def rescore_workspace(session: AsyncSession, workspace_id: UUID, now: datetime | None = None) -> int:
    rows = await session.execute(text("select id from contacts where workspace_id = :ws and deleted_at is null"), {"ws": workspace_id})
    n = 0
    for (cid,) in rows.all():
        if await rescore_contact(session, cid, now) is not None:
            n += 1
    return n
