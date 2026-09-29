from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.auth.deps import Session, Workspace

router = APIRouter(prefix="/search", tags=["search"])


class ContactHit(BaseModel):
    id: UUID
    display_name: str
    title: str | None
    company_name: str | None
    gravity_score: int


class CompanyHit(BaseModel):
    id: UUID
    name: str
    industry: str | None


class InteractionHit(BaseModel):
    id: UUID
    contact_id: UUID | None
    subject: str | None
    snippet: str
    occurred_at: str


class SearchResult(BaseModel):
    contacts: list[ContactHit]
    companies: list[CompanyHit]
    interactions: list[InteractionHit]


@router.get("", operation_id="search_global", response_model=SearchResult)
async def search_global(ws: Workspace, session: Session, q: Annotated[str, Query(min_length=1, max_length=120)]) -> SearchResult:
    contacts = (
        (
            await session.execute(
                text("select id, display_name, title, company_name, gravity_score from search_contacts(:ws, :q, 5)"),
                {"ws": ws.workspace_id, "q": q},
            )
        )
        .mappings()
        .all()
    )
    companies = (
        (
            await session.execute(
                text(
                    "select id, name, industry from companies where workspace_id = :ws and deleted_at is null "
                    "and name ilike '%' || :q || '%' order by name limit 5"
                ),
                {"ws": ws.workspace_id, "q": q},
            )
        )
        .mappings()
        .all()
    )
    interactions = (
        (
            await session.execute(
                text(
                    "select id, contact_id, subject, left(coalesce(summary, body), 160) as snippet, "
                    "occurred_at::text as occurred_at "
                    "from interactions where workspace_id = :ws and deleted_at is null "
                    "and search_vector @@ plainto_tsquery('english', :q) order by occurred_at desc limit 5"
                ),
                {"ws": ws.workspace_id, "q": q},
            )
        )
        .mappings()
        .all()
    )
    return SearchResult(
        contacts=[ContactHit(**c) for c in contacts],
        companies=[CompanyHit(**c) for c in companies],
        interactions=[InteractionHit(**i) for i in interactions],
    )
