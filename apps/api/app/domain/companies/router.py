from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.auth.deps import CurrentUser, Session, Workspace, WorkspaceContext, require_role
from app.domain.common import Page
from app.domain.companies import service
from app.domain.companies.schemas import CompanyCreate, CompanyRead, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])
Member = Annotated[WorkspaceContext, Depends(require_role("member"))]
Admin = Annotated[WorkspaceContext, Depends(require_role("admin"))]


@router.get("", operation_id="companies_list", response_model=Page[CompanyRead])
async def companies_list(
    ws: Workspace,
    session: Session,
    q: Annotated[str | None, Query(max_length=120)] = None,
    type: Annotated[str | None, Query()] = None,
    industry: Annotated[str | None, Query(max_length=60)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query()] = None,
) -> Page[CompanyRead]:
    return await service.list_companies(session, ws, q, type, industry, limit, cursor)


@router.post("", operation_id="companies_create", response_model=CompanyRead, status_code=201)
async def companies_create(body: CompanyCreate, ctx: CurrentUser, ws: Member, session: Session) -> CompanyRead:
    return await service.create(session, ws, UUID(ctx.user_id), body)


@router.get("/{company_id}", operation_id="companies_get", response_model=CompanyRead)
async def companies_get(company_id: UUID, ws: Workspace, session: Session) -> CompanyRead:
    return await service.get(session, ws, company_id)


@router.patch("/{company_id}", operation_id="companies_update", response_model=CompanyRead)
async def companies_update(company_id: UUID, body: CompanyUpdate, ws: Member, session: Session) -> CompanyRead:
    return await service.update(session, ws, company_id, body)


@router.delete("/{company_id}", operation_id="companies_delete", status_code=204)
async def companies_delete(company_id: UUID, ws: Admin, session: Session) -> Response:
    await service.delete(session, ws, company_id)
    return Response(status_code=204)
