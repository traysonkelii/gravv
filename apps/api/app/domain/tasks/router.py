from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.auth.deps import CurrentUser, Session, Workspace, WorkspaceContext, require_role
from app.domain.common import Page
from app.domain.tasks import service
from app.domain.tasks.schemas import SnoozeRequest, TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])
Member = Annotated[WorkspaceContext, Depends(require_role("member"))]


@router.get("", operation_id="tasks_list", response_model=Page[TaskRead])
async def tasks_list(
    ctx: CurrentUser,
    ws: Workspace,
    session: Session,
    status: Annotated[str | None, Query(pattern="^(open|done|snoozed|cancelled)$")] = None,
    due_before: Annotated[datetime | None, Query()] = None,
    contact_id: Annotated[UUID | None, Query()] = None,
    assignee: Annotated[str | None, Query(pattern="^me$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> Page[TaskRead]:
    return await service.list_tasks(session, ws, UUID(ctx.user_id), status, due_before, contact_id, assignee == "me", limit, cursor)


@router.post("", operation_id="tasks_create", response_model=TaskRead, status_code=201)
async def tasks_create(body: TaskCreate, ctx: CurrentUser, ws: Member, session: Session) -> TaskRead:
    return await service.create(session, ws, UUID(ctx.user_id), body)


@router.patch("/{task_id}", operation_id="tasks_update", response_model=TaskRead)
async def tasks_update(task_id: UUID, body: TaskUpdate, ws: Member, session: Session) -> TaskRead:
    return await service.update(session, ws, task_id, body)


@router.post("/{task_id}/complete", operation_id="tasks_complete", response_model=TaskRead)
async def tasks_complete(task_id: UUID, ws: Member, session: Session) -> TaskRead:
    return await service.complete(session, ws, task_id)


@router.post("/{task_id}/snooze", operation_id="tasks_snooze", response_model=TaskRead)
async def tasks_snooze(task_id: UUID, body: SnoozeRequest, ws: Member, session: Session) -> TaskRead:
    return await service.snooze(session, ws, task_id, body.until)
