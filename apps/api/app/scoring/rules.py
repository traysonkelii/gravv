"""Insight rules (Section 7.10). Rules detect deterministically from SQL inputs; each returns InsightDrafts."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GENERATED_BY = "rules:v1"
EXPIRES_DAYS = 14


@dataclass(frozen=True)
class InsightDraft:
    kind: str
    severity: str
    title: str
    body: str
    dedupe_key: str
    user_id: UUID | None = None
    contact_id: UUID | None = None
    company_id: UUID | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_action: dict[str, Any] | None = None


def _week(now: datetime) -> str:
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def _name(row: Any) -> str:
    return f"{row['honorific'] + ' ' if row['honorific'] else ''}{row['display_name']}"


async def follow_up_due(session: AsyncSession, ws: UUID, now: datetime) -> list[InsightDraft]:
    rows = (
        (
            await session.execute(
                text("""
        select c.id, c.owner_user_id, c.honorific, c.display_name, c.next_due_at, c.cadence_days, c.last_interaction_at
        from contacts c where c.workspace_id = :ws and c.deleted_at is null and c.status <> 'archived'
          and c.next_due_at is not null and c.next_due_at <= now() + interval '3 days'
          and not exists (select 1 from tasks t where t.contact_id = c.id and t.status = 'open'
                          and t.due_at <= now() + interval '3 days')
        """),
                {"ws": ws},
            )
        )
        .mappings()
        .all()
    )
    out = []
    for r in rows:
        overdue_days = int((now - r["next_due_at"]).total_seconds() // 86400) if r["next_due_at"] < now else 0
        when = f"overdue {overdue_days} day{'s' if overdue_days != 1 else ''}" if overdue_days else "due within 3 days"
        out.append(
            InsightDraft(
                kind="follow_up",
                severity="notice" if overdue_days else "info",
                title=f"Follow up with {_name(r)}",
                body=f"Their {r['cadence_days']}-day orbit is {when}. No follow-up task is scheduled.",
                dedupe_key=f"follow_up:{r['id']}:{_week(now)}",
                user_id=r["owner_user_id"],
                contact_id=r["id"],
                evidence={
                    "next_due_at": r["next_due_at"].isoformat(),
                    "cadence_days": r["cadence_days"],
                    "last_interaction_at": r["last_interaction_at"].isoformat() if r["last_interaction_at"] else None,
                },
                suggested_action={
                    "type": "create_task",
                    "payload": {
                        "title": f"Follow up with {_name(r)}",
                        "contact_id": str(r["id"]),
                        "due_at": (now + timedelta(days=2)).isoformat(),
                    },
                },
            )
        )
    return out


async def at_risk(session: AsyncSession, ws: UUID, now: datetime) -> list[InsightDraft]:
    rows = (
        (
            await session.execute(
                text("""
        with latest as (
          select distinct on (rs.contact_id) rs.contact_id, rs.band, rs.score, rs.scored_on
          from relationship_scores rs join contacts c on c.id = rs.contact_id
          where c.workspace_id = :ws order by rs.contact_id, rs.scored_on desc)
        select c.id, c.owner_user_id, c.honorific, c.display_name, c.last_interaction_at, l.band, l.score,
          (select rs.score from relationship_scores rs where rs.contact_id = c.id and rs.scored_on <= l.scored_on - 30
             order by rs.scored_on desc limit 1) as score_30d_ago,
          (select count(*) from interactions i where i.contact_id = c.id and i.deleted_at is null) as n_interactions
        from contacts c join latest l on l.contact_id = c.id
        where c.workspace_id = :ws and c.deleted_at is null and c.status <> 'archived'
        """),
                {"ws": ws},
            )
        )
        .mappings()
        .all()
    )
    out = []
    for r in rows:
        delta = (r["score"] - r["score_30d_ago"]) if r["score_30d_ago"] is not None else None
        decayed = r["band"] in ("weak", "drifting") and r["n_interactions"] > 0
        if not (decayed or (delta is not None and delta <= -10)):
            continue
        if delta is not None and delta <= -10:
            body = f"Gravity dropped {abs(delta)} points in 30 days."
        else:
            since = r["last_interaction_at"]
            days = int((now - since).total_seconds() // 86400) if since else None
            body = f"The relationship is {r['band']}: last contact {days} days ago." if days is not None else "The relationship is weak."
        out.append(
            InsightDraft(
                kind="at_risk",
                severity="warning",
                title=f"{_name(r)} needs attention",
                body=body,
                dedupe_key=f"at_risk:{r['id']}:{_week(now)}",
                user_id=r["owner_user_id"],
                contact_id=r["id"],
                evidence={
                    "band": r["band"],
                    "score": r["score"],
                    "delta_30d": delta,
                    "interactions": int(r["n_interactions"]),
                },
                suggested_action={
                    "type": "create_task",
                    "payload": {
                        "title": f"Re-engage {_name(r)}",
                        "contact_id": str(r["id"]),
                        "due_at": (now + timedelta(days=3)).isoformat(),
                    },
                },
            )
        )
    return out


async def opportunity_signal(session: AsyncSession, ws: UUID, now: datetime) -> list[InsightDraft]:
    rows = (
        (
            await session.execute(
                text("""
        select co.id, co.name, count(distinct c.id) as active_contacts,
               sum(case when (c.gravity_score - coalesce((select rs.score from relationship_scores rs where rs.contact_id = c.id
                    and rs.scored_on <= current_date - 30 order by rs.scored_on desc limit 1), c.gravity_score)) > 0 then 1 else 0 end) as rising
        from companies co join contacts c on c.company_id = co.id and c.deleted_at is null
        where co.workspace_id = :ws and co.deleted_at is null
          and exists (select 1 from interactions i where i.contact_id = c.id and i.deleted_at is null
                      and i.occurred_at >= now() - interval '14 days')
        group by co.id, co.name having count(distinct c.id) >= 3
        """),
                {"ws": ws},
            )
        )
        .mappings()
        .all()
    )
    return [
        InsightDraft(
            kind="opportunity_signal",
            severity="info",
            title=f"{r['name']} activity rising",
            body=f"{r['active_contacts']} contacts at {r['name']} were active in the last two weeks.",
            dedupe_key=f"opportunity_signal:{r['id']}:{_week(now)}",
            company_id=r["id"],
            evidence={"active_contacts": int(r["active_contacts"]), "rising": int(r["rising"] or 0)},
            suggested_action={"type": "open_company", "payload": {"company_id": str(r["id"])}},
        )
        for r in rows
    ]


async def introduction_path(session: AsyncSession, ws: UUID, now: datetime) -> list[InsightDraft]:
    rows = (
        (
            await session.execute(
                text("""
        select co.id as company_id, co.name as company_name, s.id as strong_id, s.honorific, s.display_name,
               t.id as target_id, t.display_name as target_name, s.owner_user_id
        from companies co
        join contacts t on t.company_id = co.id and t.deleted_at is null
        join contact_edges e on (e.contact_a_id = t.id or e.contact_b_id = t.id)
        join contacts s on s.id = case when e.contact_a_id = t.id then e.contact_b_id else e.contact_a_id end
          and s.deleted_at is null and s.gravity_score >= 70 and coalesce(s.company_id, '00000000-0000-0000-0000-000000000000') <> co.id
        where co.workspace_id = :ws and co.deleted_at is null
          and not exists (select 1 from contacts x where x.company_id = co.id and x.deleted_at is null and x.gravity_score >= 40)
        """),
                {"ws": ws},
            )
        )
        .mappings()
        .all()
    )
    seen: set[UUID] = set()
    out = []
    for r in rows:
        if r["company_id"] in seen:
            continue
        seen.add(r["company_id"])
        out.append(
            InsightDraft(
                kind="introduction_path",
                severity="info",
                title=f"A path into {r['company_name']}",
                body=f"{_name(r)} knows {r['target_name']} at {r['company_name']}, where you have no strong relationship yet.",
                dedupe_key=f"introduction_path:{r['company_id']}:{_week(now)}",
                user_id=r["owner_user_id"],
                contact_id=r["strong_id"],
                company_id=r["company_id"],
                evidence={"via_contact_id": str(r["strong_id"]), "target_contact_id": str(r["target_id"])},
                suggested_action={
                    "type": "draft_message",
                    "payload": {"contact_id": str(r["strong_id"]), "about_contact_id": str(r["target_id"])},
                },
            )
        )
    return out


async def common_ground(session: AsyncSession, ws: UUID, now: datetime) -> list[InsightDraft]:
    rows = (
        (
            await session.execute(
                text("""
        select distinct c.id, c.owner_user_id, c.honorific, c.display_name, f.content, ui.value as interest
        from contact_facts f join contacts c on c.id = f.contact_id
        join user_interests ui on ui.user_id = c.owner_user_id
        where c.workspace_id = :ws and c.deleted_at is null and f.is_active and f.created_at >= now() - interval '7 days'
          and (lower(f.content) = lower(ui.value) or f.content ilike '%' || ui.value || '%')
        """),
                {"ws": ws},
            )
        )
        .mappings()
        .all()
    )
    out = []
    for r in rows:
        out.append(
            InsightDraft(
                kind="common_ground",
                severity="info",
                title=f"Common ground with {_name(r)}",
                body=f"They {r['content'][0].lower() + r['content'][1:]}; you listed {r['interest']} as an interest.",
                dedupe_key=f"common_ground:{r['id']}:{r['interest'].lower()}",
                user_id=r["owner_user_id"],
                contact_id=r["id"],
                evidence={"fact": r["content"], "interest": r["interest"]},
                suggested_action={"type": "open_contact", "payload": {"contact_id": str(r["id"])}},
            )
        )
    return out


async def trend(session: AsyncSession, ws: UUID, now: datetime) -> list[InsightDraft]:
    rows = (
        (
            await session.execute(
                text("""
        with monthly as (
          select co.id, co.name, date_trunc('month', rs.scored_on) as m, avg(rs.score) as avg_score
          from relationship_scores rs join contacts c on c.id = rs.contact_id join companies co on co.id = c.company_id
          where rs.workspace_id = :ws group by co.id, co.name, m)
        select a.id, a.name, a.avg_score as current, b.avg_score as previous
        from monthly a join monthly b on b.id = a.id and b.m = a.m - interval '1 month'
        where a.m = date_trunc('month', now()) and b.avg_score > 0
          and abs(a.avg_score - b.avg_score) / b.avg_score >= 0.10
        """),
                {"ws": ws},
            )
        )
        .mappings()
        .all()
    )
    return [
        InsightDraft(
            kind="trend",
            severity="info",
            title=f"{r['name']} gravity {'up' if r['current'] > r['previous'] else 'down'} {abs(round((r['current'] - r['previous']) / r['previous'] * 100))}%",
            body=f"Average gravity across {r['name']} contacts moved from {round(r['previous'])} to {round(r['current'])} this month.",
            dedupe_key=f"trend:{r['id']}:{now.strftime('%Y-%m')}",
            company_id=r["id"],
            evidence={"current": float(r["current"]), "previous": float(r["previous"])},
            suggested_action={"type": "open_analytics", "payload": {"company_id": str(r["id"])}},
        )
        for r in rows
    ]


RULES = [follow_up_due, at_risk, opportunity_signal, introduction_path, common_ground, trend]


async def generate_for_workspace(session: AsyncSession, ws: UUID, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    drafts: list[InsightDraft] = []
    for rule in RULES:
        drafts.extend(await rule(session, ws, now))
    written = 0
    for d in drafts:
        res = await session.execute(
            text("""
            insert into insights (workspace_id, user_id, contact_id, company_id, kind, severity, title, body, evidence,
                                  suggested_action, dedupe_key, expires_at, generated_by)
            values (:ws, :uid, :cid, :coid, cast(:kind as insight_kind), cast(:sev as insight_severity), :title, :body,
                    cast(:evidence as jsonb), cast(:action as jsonb), :key, :expires, :gen)
            on conflict (workspace_id, dedupe_key) do nothing returning id
            """),
            {
                "ws": ws,
                "uid": d.user_id,
                "cid": d.contact_id,
                "coid": d.company_id,
                "kind": d.kind,
                "sev": d.severity,
                "title": d.title,
                "body": d.body,
                "evidence": json.dumps(d.evidence, default=str),
                "action": json.dumps(d.suggested_action) if d.suggested_action else None,
                "key": d.dedupe_key,
                "expires": now + timedelta(days=EXPIRES_DAYS),
                "gen": GENERATED_BY,
            },
        )
        if res.first():
            written += 1
    await session.execute(
        text("update insights set status = 'expired' where workspace_id = :ws and status in ('new', 'seen') and expires_at < now()"),
        {"ws": ws},
    )
    return written
