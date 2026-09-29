from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import WorkspaceContext
from app.db.repositories import contacts as contacts_repo
from app.db.repositories import facts as repo
from app.domain.audit import write_audit
from app.domain.facts.schemas import FactCreate, FactRead, FactUpdate
from app.errors import Problem


async def list_facts(session: AsyncSession, ws: WorkspaceContext, contact_id: UUID, include_inactive: bool) -> list[FactRead]:
    if await contacts_repo.get_contact(session, ws.workspace_id, contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")
    return [FactRead.model_validate(f) for f in await repo.list_facts(session, contact_id, include_inactive)]


async def create_fact(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, contact_id: UUID, body: FactCreate) -> FactRead:
    if await contacts_repo.get_contact(session, ws.workspace_id, contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")
    if await repo.find_active_duplicate(session, contact_id, body.content):
        raise Problem(409, "conflict", "Already recorded", "This note is already on the contact.")
    fact = await repo.create_fact(
        session, {**body.model_dump(), "workspace_id": ws.workspace_id, "contact_id": contact_id, "created_by": user_id}
    )
    await write_audit(session, ws.workspace_id, "fact.create", "contact_fact", fact.id, {"contact_id": str(contact_id)})
    return FactRead.model_validate(fact)


async def update_fact(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, fact_id: UUID, body: FactUpdate) -> FactRead:
    fact = await repo.get_fact(session, ws.workspace_id, fact_id)
    if fact is None:
        raise Problem(404, "not_found", "Note not found")
    if not fact.is_active:
        raise Problem(409, "conflict", "Note is archived", "Archived notes cannot be edited.")
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return FactRead.model_validate(fact)
    new = await repo.supersede(session, fact, fields, user_id)
    await write_audit(session, ws.workspace_id, "fact.supersede", "contact_fact", new.id, {"previous": str(fact.id)})
    return FactRead.model_validate(new)


async def delete_fact(session: AsyncSession, ws: WorkspaceContext, fact_id: UUID) -> None:
    fact = await repo.get_fact(session, ws.workspace_id, fact_id)
    if fact is None:
        raise Problem(404, "not_found", "Note not found")
    await repo.deactivate(session, fact)
    await write_audit(session, ws.workspace_id, "fact.deactivate", "contact_fact", fact.id)
