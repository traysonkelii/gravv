from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import text

from app.auth.deps import CurrentUser, Session, Workspace, WorkspaceContext, require_role
from app.domain.network import service
from app.domain.network.schemas import EdgeCreate, EdgeRead, Graph, PathsResult

router = APIRouter(tags=["network"])
Member = Annotated[WorkspaceContext, Depends(require_role("member"))]


async def _user_name(session: Session, ctx: CurrentUser) -> str:
    return str(await session.scalar(text("select full_name from profiles where id = auth.uid()")) or "You")


@router.get("/contacts/{contact_id}/edges", operation_id="edges_list", response_model=list[EdgeRead])
async def edges_list(contact_id: UUID, ws: Workspace, session: Session) -> list[EdgeRead]:
    return await service.list_edges(session, ws, contact_id)


@router.post("/contacts/{contact_id}/edges", operation_id="edges_create", response_model=EdgeRead, status_code=201)
async def edges_create(contact_id: UUID, body: EdgeCreate, ctx: CurrentUser, ws: Member, session: Session) -> EdgeRead:
    return await service.create_edge(session, ws, UUID(ctx.user_id), contact_id, body)


@router.delete("/edges/{edge_id}", operation_id="edges_delete", status_code=204)
async def edges_delete(edge_id: UUID, ws: Member, session: Session) -> Response:
    await service.delete_edge(session, ws, edge_id)
    return Response(status_code=204)


@router.get("/network/graph", operation_id="network_graph", response_model=Graph)
async def network_graph(
    ctx: CurrentUser,
    ws: Workspace,
    session: Session,
    relationship_type: Annotated[str | None, Query()] = None,
    industry: Annotated[str | None, Query(max_length=60)] = None,
    min_score: Annotated[int, Query(ge=0, le=100)] = 0,
) -> Graph:
    return await service.graph(session, ws, UUID(ctx.user_id), await _user_name(session, ctx), relationship_type, industry, min_score)


@router.get("/network/paths", operation_id="network_paths", response_model=PathsResult)
async def network_paths(
    ctx: CurrentUser,
    ws: Workspace,
    session: Session,
    to: Annotated[str, Query(min_length=1, max_length=120)],
    from_: Annotated[str, Query(alias="from", max_length=36)] = "me",
) -> PathsResult:
    return await service.paths(session, ws, UUID(ctx.user_id), await _user_name(session, ctx), from_, to)
