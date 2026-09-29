from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import WorkspaceContext
from app.db.models import Interaction
from app.db.repositories import contacts as contacts_repo
from app.db.repositories import interactions as repo
from app.domain.audit import write_audit
from app.domain.common import Page, decode_cursor, encode_cursor, page_of
from app.domain.contacts.service import touch_last_interaction
from app.domain.interactions.schemas import InteractionCreate, InteractionRead, InteractionUpdate
from app.errors import Problem


async def list_interactions(
    session: AsyncSession, ws: WorkspaceContext, f: repo.InteractionFilters, limit: int, cursor: str | None
) -> Page[InteractionRead]:
    rows = await repo.list_interactions(session, ws.workspace_id, f, limit, decode_cursor(cursor))
    items, next_cursor = page_of(rows, limit, lambda i: encode_cursor(i.occurred_at.isoformat(), i.id))
    return Page(items=[InteractionRead.model_validate(i) for i in items], next_cursor=next_cursor)


async def create_interaction(
    session: AsyncSession, ws: WorkspaceContext, user_id: UUID, body: InteractionCreate
) -> InteractionRead:
    if await contacts_repo.get_contact(session, ws.workspace_id, body.contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")
    fields = body.model_dump(exclude={"extract"})
    fields["occurred_at"] = body.occurred_at or datetime.now(UTC)
    fields.update(workspace_id=ws.workspace_id, user_id=user_id)
    row = await repo.create_interaction(session, fields)
    await write_audit(
        session,
        ws.workspace_id,
        "interaction.create",
        "interaction",
        row.id,
        {"contact_id": str(body.contact_id), "kind": body.kind.value},
    )
    if body.extract and body.body.strip():
        from app.domain.captures.service import create_for_interaction

        await create_for_interaction(session, ws, user_id, row.id, body.contact_id, body.body)
    return InteractionRead.model_validate(row)


async def _load_for_write(
    session: AsyncSession, ws: WorkspaceContext, user_id: UUID, interaction_id: UUID
) -> Interaction:
    row = await repo.get_interaction(session, ws.workspace_id, interaction_id)
    if row is None:
        raise Problem(404, "not_found", "Interaction not found")
    if row.user_id != user_id and not ws.at_least("manager"):
        raise Problem(
            403, "insufficient_role", "Insufficient role", "Editing another person's note requires the manager role."
        )
    return row


async def update_interaction(
    session: AsyncSession, ws: WorkspaceContext, user_id: UUID, interaction_id: UUID, body: InteractionUpdate
) -> InteractionRead:
    row = await _load_for_write(session, ws, user_id, interaction_id)
    fields = body.model_dump(exclude_unset=True)
    row = await repo.update_interaction(session, row, fields)
    if row.contact_id is not None:
        await touch_last_interaction(session, row.contact_id)
    await write_audit(session, ws.workspace_id, "interaction.update", "interaction", row.id, fields)
    return InteractionRead.model_validate(row)


async def delete_interaction(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, interaction_id: UUID) -> None:
    row = await _load_for_write(session, ws, user_id, interaction_id)
    await repo.soft_delete_interaction(session, row)
    if row.contact_id is not None:
        await touch_last_interaction(session, row.contact_id)
    await write_audit(session, ws.workspace_id, "interaction.delete", "interaction", row.id)
