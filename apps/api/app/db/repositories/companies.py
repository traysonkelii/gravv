from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company


async def list_companies(
    session: AsyncSession,
    ws: UUID,
    q: str | None,
    type_: str | None,
    industry: str | None,
    limit: int,
    after: tuple[str, str] | None,
) -> list[Company]:
    stmt = select(Company).where(Company.workspace_id == ws, Company.deleted_at.is_(None))
    if q:
        stmt = stmt.where(Company.name.ilike(f"%{q}%"))
    if type_:
        stmt = stmt.where(Company.type == type_)
    if industry:
        stmt = stmt.where(func.lower(Company.industry) == industry.lower())
    if after:
        stmt = stmt.where(func.row(func.lower(Company.name), Company.id) > func.row(after[0], UUID(after[1])))
    stmt = stmt.order_by(func.lower(Company.name), Company.id).limit(limit + 1)
    return list(await session.scalars(stmt))


async def get_company(session: AsyncSession, ws: UUID, company_id: UUID) -> Company | None:
    return await session.scalar(
        select(Company).where(Company.id == company_id, Company.workspace_id == ws, Company.deleted_at.is_(None))
    )


async def find_by_name(session: AsyncSession, ws: UUID, name: str) -> Company | None:
    return await session.scalar(
        select(Company)
        .where(
            Company.workspace_id == ws, Company.deleted_at.is_(None), func.lower(Company.name) == name.strip().lower()
        )
        .limit(1)
    )


async def create_company(session: AsyncSession, ws: UUID, created_by: UUID, fields: dict[str, Any]) -> Company:
    company = Company(workspace_id=ws, created_by=created_by, **fields)
    session.add(company)
    await session.flush()
    await session.refresh(company)
    return company


async def find_or_create(session: AsyncSession, ws: UUID, created_by: UUID, name: str) -> Company:
    existing = await find_by_name(session, ws, name)
    if existing:
        return existing
    return await create_company(session, ws, created_by, {"name": name.strip()})


async def update_company(session: AsyncSession, company: Company, fields: dict[str, Any]) -> Company:
    for k, v in fields.items():
        setattr(company, k, v)
    await session.flush()
    await session.refresh(company)
    return company


async def soft_delete_company(session: AsyncSession, company: Company) -> None:
    await session.execute(update(Company).where(Company.id == company.id).values(deleted_at=func.now()))
