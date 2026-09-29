from uuid import UUID

from fastapi import APIRouter, Response

from app.auth.deps import CurrentUser, Session, Workspace
from app.domain.ai_credentials import service
from app.domain.ai_credentials.schemas import AIStatusRead, CredentialPut, CredentialRead, Provider
from app.errors import Problem

router = APIRouter(prefix="/workspaces/{workspace_id}/ai", tags=["ai"])


def _same(ws: Workspace, workspace_id: UUID) -> None:
    if ws.workspace_id != workspace_id:
        raise Problem(400, "bad_request", "Bad request", "Send X-Workspace-Id matching the workspace in the path.")


@router.get("", operation_id="ai_status", response_model=AIStatusRead)
async def ai_status(workspace_id: UUID, ws: Workspace, session: Session) -> AIStatusRead:
    _same(ws, workspace_id)
    return await service.status(session, ws)


@router.put("/{provider}", operation_id="ai_credential_put", response_model=CredentialRead)
async def ai_credential_put(
    workspace_id: UUID, provider: Provider, body: CredentialPut, ctx: CurrentUser, ws: Workspace, session: Session
) -> CredentialRead:
    _same(ws, workspace_id)
    return await service.put(session, ws, UUID(ctx.user_id), provider, body)


@router.delete("/{provider}", operation_id="ai_credential_delete", status_code=204)
async def ai_credential_delete(workspace_id: UUID, provider: Provider, ws: Workspace, session: Session) -> Response:
    _same(ws, workspace_id)
    await service.delete(session, ws, provider)
    return Response(status_code=204)
