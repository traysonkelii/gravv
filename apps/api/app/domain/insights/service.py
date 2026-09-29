from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import WorkspaceContext
from app.domain.audit import write_audit
from app.domain.insights.schemas import InsightActResult, InsightRead
from app.errors import Problem
from app.jobs import queue

_SELECT = """
select i.id, i.workspace_id, i.user_id, i.contact_id, i.company_id, i.kind::text, i.severity::text, i.title, i.body,
       i.evidence, i.suggested_action, i.status::text, i.expires_at, i.generated_by, i.created_at,
       case when c.id is null then null else coalesce(c.honorific || ' ', '') || c.display_name end as contact_name,
       co.name as company_name
from insights i left join contacts c on c.id = i.contact_id left join companies co on co.id = i.company_id
"""


def _read(r: Any) -> InsightRead:
    return InsightRead(
        id=r["id"],
        workspace_id=r["workspace_id"],
        user_id=r["user_id"],
        contact_id=r["contact_id"],
        contact_name=r["contact_name"],
        company_id=r["company_id"],
        company_name=r["company_name"],
        kind=r["kind"],
        severity=r["severity"],
        title=r["title"],
        body=r["body"],
        evidence=r["evidence"] or {},
        suggested_action=r["suggested_action"],
        status=r["status"],
        expires_at=r["expires_at"],
        generated_by=r["generated_by"],
        created_at=r["created_at"],
    )


async def list_insights(
    session: AsyncSession,
    ws: WorkspaceContext,
    user_id: UUID,
    status: str | None,
    kind: str | None,
    contact_id: UUID | None,
    scope: str,
    limit: int,
) -> list[InsightRead]:
    if scope == "team" and not ws.at_least("manager"):
        raise Problem(403, "insufficient_role", "Insufficient role", "Team insights require the manager role.")
    params: dict[str, Any] = {"ws": ws.workspace_id, "lim": limit, "uid": user_id}
    where = ["i.workspace_id = :ws"]
    where.append("(i.user_id = :uid or i.user_id is null)" if scope != "team" else "true")
    if status:
        where.append("i.status = cast(:status as insight_status)")
        params["status"] = status
    if kind:
        where.append("i.kind = cast(:kind as insight_kind)")
        params["kind"] = kind
    if contact_id:
        where.append("i.contact_id = :cid")
        params["cid"] = contact_id
    sql = f"{_SELECT} where {' and '.join(where)} order by case i.severity when 'warning' then 0 when 'notice' then 1 else 2 end, i.created_at desc limit :lim"
    rows = (await session.execute(text(sql), params)).mappings().all()
    return [_read(r) for r in rows]


async def _get(session: AsyncSession, ws: WorkspaceContext, insight_id: UUID) -> InsightRead:
    r = (
        (await session.execute(text(f"{_SELECT} where i.id = :id and i.workspace_id = :ws"), {"id": insight_id, "ws": ws.workspace_id}))
        .mappings()
        .first()
    )
    if r is None:
        raise Problem(404, "not_found", "Insight not found")
    return _read(r)


async def set_status(session: AsyncSession, ws: WorkspaceContext, insight_id: UUID, status: str) -> InsightRead:
    await _get(session, ws, insight_id)
    await session.execute(text("update insights set status = cast(:s as insight_status) where id = :id"), {"id": insight_id, "s": status})
    return await _get(session, ws, insight_id)


async def act(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, insight_id: UUID) -> InsightActResult:
    insight = await _get(session, ws, insight_id)
    action = insight.suggested_action or {}
    payload = action.get("payload") or {}
    task_id: UUID | None = None
    navigate: str | None = None
    kind = action.get("type")
    if kind == "create_task":
        due = payload.get("due_at")
        task_id = await session.scalar(
            text(
                "insert into tasks (workspace_id, assignee_user_id, contact_id, title, due_at, priority, source, created_by) "
                "values (:ws, :u, :cid, :t, :due, 2, 'ai', :u) returning id"
            ),
            {
                "ws": ws.workspace_id,
                "u": user_id,
                "cid": payload.get("contact_id"),
                "t": payload.get("title", insight.title)[:200],
                "due": datetime.fromisoformat(due) if due else None,
            },
        )
        navigate = f"/app/contacts/{payload.get('contact_id')}?tab=tasks" if payload.get("contact_id") else "/app/tasks"
    elif kind == "open_contact":
        navigate = f"/app/contacts/{payload.get('contact_id')}"
    elif kind == "open_company":
        navigate = f"/app/contacts?company_id={payload.get('company_id')}"
    elif kind == "open_analytics":
        navigate = "/app/analytics"
    elif kind == "draft_message" or kind == "open_brief":
        navigate = f"/app/contacts/{payload.get('contact_id')}"
    await session.execute(text("update insights set status = 'acted' where id = :id"), {"id": insight_id})
    await write_audit(
        session,
        ws.workspace_id,
        "insight.act",
        "insight",
        insight_id,
        {"action": kind, "task_id": str(task_id) if task_id else None},
    )
    return InsightActResult(insight=await _get(session, ws, insight_id), task_id=task_id, navigate_to=navigate)


async def generate_now(session: AsyncSession, ws: WorkspaceContext) -> UUID | None:
    """Manager-triggered run, rate limited to one per ten minutes per workspace."""
    last = await session.scalar(text("select max(created_at) from insights where workspace_id = :ws"), {"ws": ws.workspace_id})
    if last is not None and (datetime.now(UTC) - last).total_seconds() < 600:
        raise Problem(429, "rate_limited", "Too many requests", "Insights were generated less than ten minutes ago.")
    key = f"insights.generate:{ws.workspace_id}:{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M')}"
    return await queue.enqueue(
        session,
        "insights.generate",
        {"workspace_id": str(ws.workspace_id)},
        ws.workspace_id,
        priority=4,
        dedupe_key=key,
    )
