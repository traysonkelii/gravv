from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Interaction


@dataclass(frozen=True)
class InteractionFilters:
    contact_id: UUID | None = None
    kind: str | None = None
    since: datetime | None = None
    until: datetime | None = None


async def list_interactions(
    session: AsyncSession, ws: UUID, f: InteractionFilters, limit: int, after: list[Any] | None
) -> list[Interaction]:
    stmt = select(Interaction).where(Interaction.workspace_id == ws, Interaction.deleted_at.is_(None))
    if f.contact_id:
        stmt = stmt.where(Interaction.contact_id == f.contact_id)
    if f.kind:
        stmt = stmt.where(Interaction.kind == f.kind)
    if f.since:
        stmt = stmt.where(Interaction.occurred_at >= f.since)
    if f.until:
        stmt = stmt.where(Interaction.occurred_at <= f.until)
    if after:
        stmt = stmt.where(func.row(Interaction.occurred_at, Interaction.id) < func.row(datetime.fromisoformat(after[0]), UUID(after[1])))
    stmt = stmt.order_by(Interaction.occurred_at.desc(), Interaction.id.desc()).limit(limit + 1)
    return list(await session.scalars(stmt))


async def get_interaction(session: AsyncSession, ws: UUID, interaction_id: UUID) -> Interaction | None:
    return await session.scalar(
        select(Interaction).where(Interaction.id == interaction_id, Interaction.workspace_id == ws, Interaction.deleted_at.is_(None))
    )


async def create_interaction(session: AsyncSession, fields: dict[str, Any]) -> Interaction:
    row = Interaction(**fields)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def update_interaction(session: AsyncSession, row: Interaction, fields: dict[str, Any]) -> Interaction:
    for k, v in fields.items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return row


async def soft_delete_interaction(session: AsyncSession, row: Interaction) -> None:
    await session.execute(update(Interaction).where(Interaction.id == row.id).values(deleted_at=func.now()))


async def list_for_contact(session: AsyncSession, contact_id: UUID, limit: int = 30) -> list[Interaction]:
    stmt = (
        select(Interaction)
        .where(Interaction.contact_id == contact_id, Interaction.deleted_at.is_(None))
        .order_by(Interaction.occurred_at.desc())
        .limit(limit)
    )
    return list(await session.scalars(stmt))
