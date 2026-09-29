from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ContactFact


async def list_facts(session: AsyncSession, contact_id: UUID, include_inactive: bool) -> list[ContactFact]:
    stmt = select(ContactFact).where(ContactFact.contact_id == contact_id)
    if not include_inactive:
        stmt = stmt.where(ContactFact.is_active.is_(True))
    stmt = stmt.order_by(ContactFact.category, ContactFact.created_at.desc())
    return list(await session.scalars(stmt))


async def get_fact(session: AsyncSession, ws: UUID, fact_id: UUID) -> ContactFact | None:
    return await session.scalar(select(ContactFact).where(ContactFact.id == fact_id, ContactFact.workspace_id == ws))


async def find_active_duplicate(session: AsyncSession, contact_id: UUID, content: str) -> ContactFact | None:
    return await session.scalar(
        select(ContactFact)
        .where(
            ContactFact.contact_id == contact_id,
            ContactFact.is_active.is_(True),
            func.lower(func.btrim(ContactFact.content)) == content.strip().lower(),
        )
        .limit(1)
    )


async def create_fact(session: AsyncSession, fields: dict[str, Any]) -> ContactFact:
    fact = ContactFact(**fields)
    session.add(fact)
    await session.flush()
    await session.refresh(fact)
    return fact


async def supersede(session: AsyncSession, old: ContactFact, fields: dict[str, Any], created_by: UUID) -> ContactFact:
    new = ContactFact(
        workspace_id=old.workspace_id,
        contact_id=old.contact_id,
        category=fields.get("category", old.category),
        content=fields.get("content", old.content),
        confidence=fields.get("confidence", old.confidence),
        source=old.source,
        source_interaction_id=old.source_interaction_id,
        created_by=created_by,
    )
    session.add(new)
    await session.flush()
    old.is_active = False
    old.superseded_by = new.id
    await session.flush()
    await session.refresh(new)
    return new


async def deactivate(session: AsyncSession, fact: ContactFact) -> None:
    fact.is_active = False
    await session.flush()
