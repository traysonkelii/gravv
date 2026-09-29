from uuid import UUID

from fastapi import APIRouter

from app.auth.deps import CurrentUser, Session, Workspace
from app.domain.exports import service
from app.domain.exports.schemas import ExportAccepted, ExportRead, ExportRequest
from app.errors import Problem

router = APIRouter(tags=["exports"])


@router.post("/me/export", operation_id="me_export", response_model=ExportAccepted, status_code=202)
async def me_export(body: ExportRequest, ctx: CurrentUser, ws: Workspace, session: Session) -> ExportAccepted:
    workspace_id = ws.workspace_id if body.scope == "my_contributions" else None
    return await service.request_export(session, UUID(ctx.user_id), body.scope, workspace_id)


@router.get("/me/exports", operation_id="me_exports_list", response_model=list[ExportRead])
async def me_exports_list(ctx: CurrentUser, session: Session) -> list[ExportRead]:
    return await service.list_mine(session)


@router.post("/workspaces/{workspace_id}/export", operation_id="workspaces_export", response_model=ExportAccepted, status_code=202)
async def workspaces_export(workspace_id: UUID, ctx: CurrentUser, ws: Workspace, session: Session) -> ExportAccepted:
    if ws.workspace_id != workspace_id:
        raise Problem(400, "bad_request", "Bad request", "Send X-Workspace-Id matching the workspace in the path.")
    return await service.request_workspace_export(session, ws, UUID(ctx.user_id))


@router.get("/exports/{export_id}", operation_id="exports_get", response_model=ExportRead)
async def exports_get(export_id: UUID, ctx: CurrentUser, session: Session) -> ExportRead:
    return await service.get_export(session, export_id)
