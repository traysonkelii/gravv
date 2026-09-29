from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import WorkspaceContext
from app.db.repositories import contacts as contacts_repo
from app.domain.audit import write_audit
from app.domain.common import Page, decode_cursor, encode_cursor, page_of
from app.domain.tasks.schemas import TaskCreate, TaskRead, TaskUpdate
from app.errors import Problem
from app.scoring.compute import rescore_contact

_SELECT = """
select t.id, t.workspace_id, t.assignee_user_id, t.contact_id, t.title, t.description, t.due_at, t.status::text,
       t.priority, t.source::text, t.source_interaction_id, t.completed_at, t.snoozed_until, t.created_by, t.created_at,
       t.updated_at,
       case when c.id is null then null else coalesce(c.honorific || ' ', '') || c.display_name end as contact_name,
       (select full_name from member_directory m where m.user_id = t.assignee_user_id
          and m.workspace_id = t.workspace_id limit 1) as assignee_name
from tasks t left join contacts c on c.id = t.contact_id
"""


def _read(r: Any) -> TaskRead:
    return TaskRead(**{k: r[k] for k in TaskRead.model_fields})


async def _get(session: AsyncSession, ws: WorkspaceContext, task_id: UUID) -> TaskRead:
    r = (
        (await session.execute(text(f"{_SELECT} where t.id = :id and t.workspace_id = :ws"), {"id": task_id, "ws": ws.workspace_id}))
        .mappings()
        .first()
    )
    if r is None:
        raise Problem(404, "not_found", "Task not found")
    return _read(r)


async def list_tasks(
    session: AsyncSession,
    ws: WorkspaceContext,
    user_id: UUID,
    status: str | None,
    due_before: datetime | None,
    contact_id: UUID | None,
    assignee_me: bool,
    limit: int,
    cursor: str | None,
) -> Page[TaskRead]:
    params: dict[str, Any] = {"ws": ws.workspace_id, "lim": limit + 1}
    where = ["t.workspace_id = :ws"]
    if status:
        where.append("t.status = cast(:status as task_status)")
        params["status"] = status
    if due_before:
        where.append("t.due_at <= :due_before")
        params["due_before"] = due_before
    if contact_id:
        where.append("t.contact_id = :cid")
        params["cid"] = contact_id
    if assignee_me:
        where.append("t.assignee_user_id = :uid")
        params["uid"] = user_id
    after = decode_cursor(cursor)
    if after:
        where.append("(coalesce(t.due_at, '9999-12-31'::timestamptz), t.id) > (cast(:cdue as timestamptz), cast(:cid2 as uuid))")
        params["cdue"], params["cid2"] = after[0], after[1]
    sql = f"{_SELECT} where {' and '.join(where)} order by coalesce(t.due_at, '9999-12-31'::timestamptz), t.id limit :lim"
    rows = (await session.execute(text(sql), params)).mappings().all()
    items, next_cursor = page_of(
        list(rows), limit, lambda r: encode_cursor((r["due_at"] or datetime(9999, 12, 31, tzinfo=UTC)).isoformat(), r["id"])
    )
    return Page(items=[_read(r) for r in items], next_cursor=next_cursor)


async def create(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, body: TaskCreate) -> TaskRead:
    if body.contact_id and await contacts_repo.get_contact(session, ws.workspace_id, body.contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")
    task_id = await session.scalar(
        text(
            "insert into tasks (workspace_id, assignee_user_id, contact_id, title, description, due_at, priority, source, created_by) "
            "values (:ws, :assignee, :cid, :title, :desc, :due, :prio, 'manual', :u) returning id"
        ),
        {
            "ws": ws.workspace_id,
            "assignee": body.assignee_user_id or user_id,
            "cid": body.contact_id,
            "title": body.title,
            "desc": body.description,
            "due": body.due_at,
            "prio": body.priority,
            "u": user_id,
        },
    )
    assert task_id is not None
    if body.contact_id:
        await rescore_contact(session, body.contact_id)
    await write_audit(session, ws.workspace_id, "task.create", "task", task_id, {"title": body.title})
    return await _get(session, ws, task_id)


async def update(session: AsyncSession, ws: WorkspaceContext, task_id: UUID, body: TaskUpdate) -> TaskRead:
    current = await _get(session, ws, task_id)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return current
    if (
        "contact_id" in fields
        and fields["contact_id"]
        and await contacts_repo.get_contact(session, ws.workspace_id, fields["contact_id"]) is None
    ):
        raise Problem(404, "not_found", "Contact not found")
    sets = ", ".join(f"{k} = :{k}" if k != "status" else "status = cast(:status as task_status)" for k in fields)
    await session.execute(text(f"update tasks set {sets} where id = :id"), {**fields, "id": task_id})
    for cid in {current.contact_id, fields.get("contact_id")}:
        if cid:
            await rescore_contact(session, cid)
    await write_audit(session, ws.workspace_id, "task.update", "task", task_id, fields)
    return await _get(session, ws, task_id)


async def complete(session: AsyncSession, ws: WorkspaceContext, task_id: UUID) -> TaskRead:
    current = await _get(session, ws, task_id)
    if current.status != "done":
        await session.execute(
            text("update tasks set status = 'done', completed_at = now(), snoozed_until = null where id = :id"), {"id": task_id}
        )
        if current.contact_id:
            await rescore_contact(session, current.contact_id)
        await write_audit(session, ws.workspace_id, "task.complete", "task", task_id)
    return await _get(session, ws, task_id)


async def snooze(session: AsyncSession, ws: WorkspaceContext, task_id: UUID, until: datetime) -> TaskRead:
    current = await _get(session, ws, task_id)
    if until <= datetime.now(UTC):
        raise Problem(422, "validation_error", "Invalid request", "Snooze until a future time.")
    await session.execute(
        text("update tasks set status = 'snoozed', snoozed_until = :u, due_at = :u where id = :id"), {"id": task_id, "u": until}
    )
    if current.contact_id:
        await rescore_contact(session, current.contact_id)
    await write_audit(session, ws.workspace_id, "task.snooze", "task", task_id, {"until": until.isoformat()})
    return await _get(session, ws, task_id)


async def reopen_snoozed(session: AsyncSession) -> int:
    """Scheduler helper: snoozed tasks whose snooze has passed become open again."""
    res = await session.execute(
        text("update tasks set status = 'open', snoozed_until = null where status = 'snoozed' and snoozed_until <= now() returning id")
    )
    return len(res.all())
