"""scores.compute and insights.generate (nightly per workspace) and brief.generate (on request)."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.ai.budget import BudgetExceeded, check_budget, record_usage
from app.ai.extraction import BriefDraft
from app.ai.prompts import render
from app.ai.resolve import AIProviderNotConfigured, llm_from, load_workspace_keys
from app.db.session import worker_session
from app.jobs.handlers import handler
from app.jobs.queue import Job
from app.scoring.compute import rescore_workspace
from app.scoring.rules import generate_for_workspace


@handler("scores.compute")
async def scores_compute(job: Job) -> dict[str, Any]:
    ws = UUID(job.payload["workspace_id"]) if job.payload.get("workspace_id") else job.workspace_id
    if ws is None:
        raise ValueError("scores.compute needs a workspace_id")
    async with worker_session() as s:
        n = await rescore_workspace(s, ws)
    return {"contacts": n}


@handler("insights.generate")
async def insights_generate(job: Job) -> dict[str, Any]:
    ws = UUID(job.payload["workspace_id"]) if job.payload.get("workspace_id") else job.workspace_id
    if ws is None:
        raise ValueError("insights.generate needs a workspace_id")
    async with worker_session() as s:
        n = await generate_for_workspace(s, ws)
    return {"insights": n}


@handler("brief.generate")
async def brief_generate(job: Job) -> dict[str, Any]:
    contact_id = job.payload["contact_id"]
    async with worker_session() as s:
        c = (
            (
                await s.execute(
                    text(
                        "select c.id, c.workspace_id, c.owner_user_id, c.honorific, c.display_name, c.title, co.name as company, "
                        "p.summary, p.communication_style, p.remember, p.risks from contacts c "
                        "left join companies co on co.id = c.company_id left join contact_profiles p on p.contact_id = c.id "
                        "where c.id = :id and c.deleted_at is null"
                    ),
                    {"id": contact_id},
                )
            )
            .mappings()
            .first()
        )
        if c is None:
            return {"skipped": "contact missing"}
        timeline = (
            await s.execute(
                text(
                    "select to_char(occurred_at, 'YYYY-MM-DD') as d, kind::text, coalesce(nullif(summary, ''), left(body, 160)) as s "
                    "from interactions where contact_id = :id and deleted_at is null and occurred_at >= now() - interval '90 days' "
                    "order by occurred_at desc limit 40"
                ),
                {"id": contact_id},
            )
        ).all()
        tasks = (
            await s.execute(
                text("select title, to_char(due_at, 'YYYY-MM-DD') from tasks where contact_id = :id and status = 'open' order by due_at"),
                {"id": contact_id},
            )
        ).all()
        opps = (
            await s.execute(
                text(
                    "select o.name, o.value_cents, o.stage from opportunity_contacts oc join opportunities o on o.id = oc.opportunity_id "
                    "where oc.contact_id = :id and o.status = 'open' and o.deleted_at is null"
                ),
                {"id": contact_id},
            )
        ).all()
        mutual_rows = await s.execute(
            text(
                "select x.display_name from contact_edges e join contacts x on x.id = case when e.contact_a_id = :id "
                "then e.contact_b_id else e.contact_a_id end where (e.contact_a_id = :id or e.contact_b_id = :id) "
                "and x.deleted_at is null"
            ),
            {"id": contact_id},
        )
        mutual: list[str] = [str(r[0]) for r in mutual_rows.all()]
        try:
            await check_budget(s, c["workspace_id"])
        except BudgetExceeded as exc:
            return {"budget_exceeded": str(exc)}
    name = f"{c['honorific'] + ' ' if c['honorific'] else ''}{c['display_name']}"
    prompt = render(
        "brief",
        "v1",
        contact=f"{name}, {c['title'] or 'no title'} at {c['company'] or 'no company'}",
        profile=(
            f"{c['summary'] or 'no summary yet'} Style: {c['communication_style'] or 'unknown'}. "
            f"Remember: {'; '.join(c['remember'] or []) or 'nothing recorded'}. Risks: {'; '.join(c['risks'] or []) or 'none'}."
        ),
        timeline="\n".join(f"{t[0]} | {t[1]} | {t[2]}" for t in timeline) or "none",
        tasks="\n".join(f"- {t[0]}{' (due ' + t[1] + ')' if t[1] else ''}" for t in tasks) or "none",
        opportunities="\n".join(f"- {o[0]}, {o[1] / 100:,.0f} USD, {o[2]}" for o in opps) or "none",
        mutual=", ".join(str(m) for m in mutual) or "none",
    )
    async with worker_session() as s:
        keys = await load_workspace_keys(s, c["workspace_id"])
    try:
        llm = llm_from(keys)
    except AIProviderNotConfigured as exc:
        return {"skipped": str(exc)}
    result = await llm.complete_structured(prompt=prompt, schema=BriefDraft, max_tokens=2048)
    draft = result.value
    now = datetime.now(UTC)
    async with worker_session() as s:
        await record_usage(s, c["workspace_id"], job.user_id, "brief.generate", result.model, result.usage)
        insight_id = await s.scalar(
            text("""
            insert into insights (workspace_id, user_id, contact_id, kind, severity, title, body, evidence, suggested_action,
                                  dedupe_key, expires_at, generated_by)
            values (:ws, :uid, :cid, 'briefing', 'info', :title, :body, cast(:evidence as jsonb),
                    cast(:action as jsonb), :key, :expires, :gen)
            on conflict (workspace_id, dedupe_key) do update set body = excluded.body, evidence = excluded.evidence,
                  status = 'new', expires_at = excluded.expires_at, generated_by = excluded.generated_by, updated_at = now()
            returning id
            """),
            {
                "ws": c["workspace_id"],
                "uid": job.user_id or c["owner_user_id"],
                "cid": contact_id,
                "title": f"Brief for {name}",
                "body": draft.text,
                "evidence": json.dumps({"structured": draft.structured.model_dump(), "model": result.model, "prompt_version": prompt.id}),
                "action": json.dumps({"type": "open_contact", "payload": {"contact_id": str(contact_id)}}),
                "key": f"briefing:{contact_id}:{now.strftime('%Y-%m-%d')}",
                "expires": now.replace(hour=23, minute=59),
                "gen": f"rules:v1+llm:{result.model}",
            },
        )
    return {"insight_id": str(insight_id), "tokens": result.usage.total}
