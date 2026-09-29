from uuid import UUID

from fastapi import APIRouter, Response

from app.auth.deps import CurrentUser, Session
from app.domain.workspaces import service
from app.domain.workspaces.schemas import (
    InvitationCreate,
    InvitationRead,
    MemberRead,
    MemberUpdate,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", operation_id="workspaces_list", response_model=list[WorkspaceRead])
async def workspaces_list(ctx: CurrentUser, session: Session) -> list[WorkspaceRead]:
    return await service.list_workspaces(session, UUID(ctx.user_id))


@router.post("", operation_id="workspaces_create", response_model=WorkspaceRead, status_code=201)
async def workspaces_create(body: WorkspaceCreate, ctx: CurrentUser, session: Session) -> WorkspaceRead:
    return await service.create_workspace(session, UUID(ctx.user_id), body)


@router.get("/{workspace_id}", operation_id="workspaces_get", response_model=WorkspaceRead)
async def workspaces_get(workspace_id: UUID, ctx: CurrentUser, session: Session) -> WorkspaceRead:
    return await service.get_workspace(session, workspace_id, UUID(ctx.user_id))


@router.patch("/{workspace_id}", operation_id="workspaces_update", response_model=WorkspaceRead)
async def workspaces_update(
    workspace_id: UUID, body: WorkspaceUpdate, ctx: CurrentUser, session: Session
) -> WorkspaceRead:
    return await service.update_workspace(session, workspace_id, UUID(ctx.user_id), body)


@router.get("/{workspace_id}/members", operation_id="members_list", response_model=list[MemberRead])
async def members_list(workspace_id: UUID, ctx: CurrentUser, session: Session) -> list[MemberRead]:
    return await service.list_members(session, workspace_id, UUID(ctx.user_id))


@router.delete("/{workspace_id}/members/me", operation_id="members_leave", status_code=204)
async def members_leave(workspace_id: UUID, ctx: CurrentUser, session: Session) -> Response:
    await service.leave(session, workspace_id, UUID(ctx.user_id))
    return Response(status_code=204)


@router.patch("/{workspace_id}/members/{user_id}", operation_id="members_update", response_model=MemberRead)
async def members_update(
    workspace_id: UUID, user_id: UUID, body: MemberUpdate, ctx: CurrentUser, session: Session
) -> MemberRead:
    return await service.update_member(session, workspace_id, ctx, user_id, body)


@router.post(
    "/{workspace_id}/invitations", operation_id="invitations_create", response_model=InvitationRead, status_code=201
)
async def invitations_create(
    workspace_id: UUID, body: InvitationCreate, ctx: CurrentUser, session: Session
) -> InvitationRead:
    return await service.invite(session, workspace_id, UUID(ctx.user_id), body)


@router.get("/{workspace_id}/invitations", operation_id="invitations_list", response_model=list[InvitationRead])
async def invitations_list(workspace_id: UUID, ctx: CurrentUser, session: Session) -> list[InvitationRead]:
    return await service.list_invitations(session, workspace_id, UUID(ctx.user_id))


@router.delete("/{workspace_id}/invitations/{invitation_id}", operation_id="invitations_revoke", status_code=204)
async def invitations_revoke(workspace_id: UUID, invitation_id: UUID, ctx: CurrentUser, session: Session) -> Response:
    await service.revoke_invitation(session, workspace_id, UUID(ctx.user_id), invitation_id)
    return Response(status_code=204)
