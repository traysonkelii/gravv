from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import WorkspaceContext
from app.db.repositories import companies as repo
from app.domain.audit import write_audit
from app.domain.common import Page, decode_cursor, encode_cursor, page_of
from app.domain.companies.schemas import CompanyCreate, CompanyRead, CompanyUpdate
from app.errors import Problem


async def list_companies(
    session: AsyncSession,
    ws: WorkspaceContext,
    q: str | None,
    type_: str | None,
    industry: str | None,
    limit: int,
    cursor: str | None,
) -> Page[CompanyRead]:
    after = decode_cursor(cursor)
    rows = await repo.list_companies(session, ws.workspace_id, q, type_, industry, limit, (after[0], after[1]) if after else None)
    items, next_cursor = page_of(rows, limit, lambda c: encode_cursor(c.name.lower(), c.id))
    return Page(items=[CompanyRead.model_validate(c) for c in items], next_cursor=next_cursor)


async def create(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, body: CompanyCreate) -> CompanyRead:
    existing = await repo.find_by_name(session, ws.workspace_id, body.name)
    if existing:
        raise Problem(409, "conflict", "Company already exists", f"{existing.name} is already in this workspace.")
    company = await repo.create_company(session, ws.workspace_id, user_id, body.model_dump())
    await write_audit(session, ws.workspace_id, "company.create", "company", company.id, {"name": company.name})
    return CompanyRead.model_validate(company)


async def get(session: AsyncSession, ws: WorkspaceContext, company_id: UUID) -> CompanyRead:
    company = await repo.get_company(session, ws.workspace_id, company_id)
    if company is None:
        raise Problem(404, "not_found", "Company not found")
    return CompanyRead.model_validate(company)


async def update(session: AsyncSession, ws: WorkspaceContext, company_id: UUID, body: CompanyUpdate) -> CompanyRead:
    company = await repo.get_company(session, ws.workspace_id, company_id)
    if company is None:
        raise Problem(404, "not_found", "Company not found")
    fields = body.model_dump(exclude_unset=True)
    company = await repo.update_company(session, company, fields)
    await write_audit(session, ws.workspace_id, "company.update", "company", company.id, fields)
    return CompanyRead.model_validate(company)


async def delete(session: AsyncSession, ws: WorkspaceContext, company_id: UUID) -> None:
    company = await repo.get_company(session, ws.workspace_id, company_id)
    if company is None:
        raise Problem(404, "not_found", "Company not found")
    await repo.soft_delete_company(session, company)
    await write_audit(session, ws.workspace_id, "company.delete", "company", company.id)
