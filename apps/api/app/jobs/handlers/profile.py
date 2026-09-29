"""profile.synthesize (Section 11.3): rewrite the AI profile for one contact when its inputs changed."""

from typing import Any

from sqlalchemy import text

from app.ai.budget import BudgetExceeded, check_budget, record_usage
from app.ai.extraction import ContactProfileDraft
from app.ai.llm import get_llm_client
from app.ai.prompts import render
from app.db.session import worker_session
from app.jobs.handlers import handler
from app.jobs.queue import Job

_CONTACT = text(
    "select c.id, c.workspace_id, c.honorific, c.display_name, c.title, co.name as company, "
    "c.relationship_type::text, c.cadence_days from contacts c left join companies co on co.id = c.company_id "
    "where c.id = :id and c.deleted_at is null"
)
_FACTS = text(
    "select category::text, content from contact_facts where contact_id = :id and is_active order by created_at"
)
_INTERACTIONS = text(
    "select to_char(occurred_at, 'YYYY-MM-DD') as d, kind::text, "
    "coalesce(nullif(summary, ''), left(body, 160)) as s, coalesce(sentiment::text, '') as sent "
    "from interactions where contact_id = :id and deleted_at is null order by occurred_at desc limit 30"
)
_TASKS = text(
    "select title, to_char(due_at, 'YYYY-MM-DD') from tasks where contact_id = :id and status = 'open' "
    "order by due_at nulls last limit 20"
)
_OPPS = text(
    "select o.name, o.value_cents, o.stage from opportunity_contacts oc "
    "join opportunities o on o.id = oc.opportunity_id "
    "where oc.contact_id = :id and o.status = 'open' and o.deleted_at is null"
)
_UPSERT = text(
    "insert into contact_profiles (contact_id, workspace_id, summary, communication_style, remember, risks, "
    "talking_points, common_ground, model, prompt_version, generated_at, stale) "
    "values (:cid, :ws, :summary, :style, :remember, :risks, :points, :common, :model, :pv, now(), false) "
    "on conflict (contact_id) do update set summary = excluded.summary, "
    "communication_style = excluded.communication_style, remember = excluded.remember, risks = excluded.risks, "
    "talking_points = excluded.talking_points, common_ground = excluded.common_ground, model = excluded.model, "
    "prompt_version = excluded.prompt_version, generated_at = now(), stale = false"
)


@handler("profile.synthesize")
async def synthesize(job: Job) -> dict[str, Any]:
    contact_id = job.payload["contact_id"]
    async with worker_session() as s:
        contact = (await s.execute(_CONTACT, {"id": contact_id})).mappings().first()
        if contact is None:
            return {"skipped": "contact missing"}
        facts = (await s.execute(_FACTS, {"id": contact_id})).all()
        interactions = (await s.execute(_INTERACTIONS, {"id": contact_id})).all()
        tasks = (await s.execute(_TASKS, {"id": contact_id})).all()
        opps = (await s.execute(_OPPS, {"id": contact_id})).all()
        interests: list[str] = []
        if job.user_id:
            rows = await s.execute(text("select value from user_interests where user_id = :uid"), {"uid": job.user_id})
            values: list[Any] = list(rows.scalars().all())
            interests = [str(v) for v in values]
        try:
            await check_budget(s, contact["workspace_id"])
        except BudgetExceeded as exc:
            return {"budget_exceeded": str(exc)}

    name = f"{contact['honorific'] + ' ' if contact['honorific'] else ''}{contact['display_name']}"
    prompt = render(
        "profile",
        "v1",
        contact=(
            f"{name}, {contact['title'] or 'no title'} at {contact['company'] or 'no company'} "
            f"({contact['relationship_type']}, {contact['cadence_days']}-day cadence)"
        ),
        user_interests=", ".join(interests) or "none",
        facts="\n".join(f"- {f[0]}: {f[1]}" for f in facts) or "none",
        interactions="\n".join(f"{i[0]} | {i[1]} | {i[2]}{' | ' + i[3] if i[3] else ''}" for i in interactions)
        or "none",
        tasks="\n".join(f"- {t[0]}{' (due ' + t[1] + ')' if t[1] else ''}" for t in tasks) or "none",
        opportunities="\n".join(f"- {o[0]}, {o[1] / 100:,.0f} USD, {o[2]}" for o in opps) or "none",
    )
    llm = get_llm_client()
    result = await llm.complete_structured(prompt=prompt, schema=ContactProfileDraft, max_tokens=2048)
    draft = result.value
    async with worker_session() as s:
        await record_usage(s, contact["workspace_id"], job.user_id, "profile.synthesize", result.model, result.usage)
        await s.execute(
            _UPSERT,
            {
                "cid": contact_id,
                "ws": contact["workspace_id"],
                "summary": draft.summary,
                "style": draft.communication_style or None,
                "remember": draft.remember,
                "risks": draft.risks,
                "points": draft.talking_points,
                "common": draft.common_ground,
                "model": result.model,
                "pv": prompt.id,
            },
        )
    return {"remember": len(draft.remember), "tokens": result.usage.total}
