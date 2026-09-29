import hashlib
import secrets
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import ROLE_RANK
from app.auth.jwt import AuthContext
from app.config import get_settings
from app.db.enums import MembershipStatus, WorkspaceKind, WorkspaceRole
from app.db.models import Membership
from app.db.repositories import invitations as inv_repo
from app.db.repositories import profiles as profiles_repo
from app.db.repositories import workspaces as repo
from app.domain.workspaces.schemas import (
    InvitationCreate,
    InvitationRead,
    MemberRead,
    MemberUpdate,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.email import send_email
from app.errors import Problem


def _rank(role: WorkspaceRole | str) -> int:
    return ROLE_RANK[str(role.value if isinstance(role, WorkspaceRole) else role)]


async def _require_membership(session: AsyncSession, ws_id: UUID, user_id: UUID, min_role: str) -> Membership:
    m = await repo.get_membership(session, ws_id, user_id)
    if m is None or m.status != MembershipStatus.active:
        raise Problem(403, "not_a_member", "Not a member", "You are not an active member of this workspace.")
    if _rank(m.role) < ROLE_RANK[min_role]:
        raise Problem(
            403, "insufficient_role", "Insufficient role", f"This action requires the {min_role} role or higher."
        )
    return m


async def list_workspaces(session: AsyncSession, user_id: UUID) -> list[WorkspaceRead]:
    rows = await repo.list_memberships(session, user_id)
    out = []
    for m, ws in rows:
        if m.status != MembershipStatus.active:
            continue
        item = WorkspaceRead.model_validate(ws)
        item.my_role = m.role
        out.append(item)
    return out


async def create_workspace(session: AsyncSession, user_id: UUID, body: WorkspaceCreate) -> WorkspaceRead:
    ws_id = await repo.create_organization(session, body.name, body.slug, body.settings.model_dump())
    ws = await repo.get_workspace(session, ws_id)
    assert ws is not None
    profile = await profiles_repo.get_profile(session, user_id)
    if profile is not None and (
        profile.default_workspace_id is None
        or (await repo.get_workspace(session, profile.default_workspace_id)) is None
    ):
        await profiles_repo.update_profile(session, profile, {"default_workspace_id": ws_id})
    item = WorkspaceRead.model_validate(ws)
    item.my_role = WorkspaceRole.owner
    return item


async def get_workspace(session: AsyncSession, ws_id: UUID, user_id: UUID) -> WorkspaceRead:
    m = await _require_membership(session, ws_id, user_id, "viewer")
    ws = await repo.get_workspace(session, ws_id)
    if ws is None:
        raise Problem(404, "not_found", "Workspace not found")
    item = WorkspaceRead.model_validate(ws)
    item.my_role = m.role
    return item


async def update_workspace(session: AsyncSession, ws_id: UUID, user_id: UUID, body: WorkspaceUpdate) -> WorkspaceRead:
    m = await _require_membership(session, ws_id, user_id, "admin")
    ws = await repo.get_workspace(session, ws_id)
    if ws is None:
        raise Problem(404, "not_found", "Workspace not found")
    fields = body.model_dump(exclude_unset=True)
    if ws.kind == WorkspaceKind.personal and "slug" in fields:
        raise Problem(422, "validation_error", "Invalid request", "Personal workspaces have no slug.")
    if "settings" in fields and body.settings is not None:
        fields["settings"] = {**ws.settings, **body.settings.model_dump()}
    await repo.update_workspace(session, ws, fields)
    item = WorkspaceRead.model_validate(ws)
    item.my_role = m.role
    return item


async def list_members(session: AsyncSession, ws_id: UUID, user_id: UUID) -> list[MemberRead]:
    await _require_membership(session, ws_id, user_id, "member")
    rows = await repo.list_members(session, ws_id)
    return [
        MemberRead(
            user_id=r[0],
            full_name=r[1],
            role_title=r[2],
            avatar_path=r[3],
            email=r[4],
            role=r[5],
            status=r[6],
            joined_at=r[7],
            departed_at=r[8],
        )
        for r in rows
    ]


async def update_member(
    session: AsyncSession, ws_id: UUID, actor: AuthContext, target_user_id: UUID, body: MemberUpdate
) -> MemberRead:
    actor_id = UUID(actor.user_id)
    me = await _require_membership(session, ws_id, actor_id, "admin")
    target = await repo.get_membership(session, ws_id, target_user_id)
    if target is None:
        raise Problem(404, "not_found", "Member not found")
    ws = await repo.get_workspace(session, ws_id)
    assert ws is not None
    if ws.kind == WorkspaceKind.personal:
        raise Problem(422, "validation_error", "Invalid request", "Personal workspaces have a single owner.")

    if body.role is not None and body.role != target.role:
        if body.role == WorkspaceRole.owner:
            if me.role != WorkspaceRole.owner:
                raise Problem(403, "insufficient_role", "Insufficient role", "Only the owner can transfer ownership.")
            if actor.aal != "aal2":
                raise Problem(
                    403,
                    "mfa_required",
                    "Multi-factor authentication required",
                    "Verify a second factor before transferring ownership.",
                )
            if target.status != MembershipStatus.active:
                raise Problem(422, "validation_error", "Invalid request", "The new owner must be an active member.")
            await repo.transfer_ownership(session, ws, me, target)
        else:
            if target.user_id == actor_id:
                raise Problem(422, "validation_error", "Invalid request", "You cannot change your own role.")
            if _rank(target.role) >= _rank(me.role) or _rank(body.role) >= _rank(me.role):
                raise Problem(
                    403, "insufficient_role", "Insufficient role", "You can only assign roles below your own."
                )
            await repo.set_role(session, target, body.role)

    if body.status is not None and body.status != target.status:
        if body.status != MembershipStatus.departed:
            raise Problem(422, "validation_error", "Invalid request", "Status can only be set to departed.")
        if target.role == WorkspaceRole.owner:
            raise Problem(422, "validation_error", "Invalid request", "Transfer ownership before removing the owner.")
        if target.user_id != actor_id and _rank(target.role) >= _rank(me.role):
            raise Problem(403, "insufficient_role", "Insufficient role", "You can only remove members below your role.")
        await repo.depart(session, target)

    rows = [r for r in await repo.list_members(session, ws_id) if r[0] == target_user_id]
    r = rows[0]
    return MemberRead(
        user_id=r[0],
        full_name=r[1],
        role_title=r[2],
        avatar_path=r[3],
        email=r[4],
        role=r[5],
        status=r[6],
        joined_at=r[7],
        departed_at=r[8],
    )


async def leave(session: AsyncSession, ws_id: UUID, user_id: UUID) -> None:
    m = await _require_membership(session, ws_id, user_id, "viewer")
    ws = await repo.get_workspace(session, ws_id)
    assert ws is not None
    if ws.kind == WorkspaceKind.personal:
        raise Problem(422, "validation_error", "Invalid request", "You cannot leave your personal workspace.")
    if m.role == WorkspaceRole.owner:
        raise Problem(422, "validation_error", "Invalid request", "Transfer ownership before leaving.")
    await repo.depart(session, m)
    profile = await profiles_repo.get_profile(session, user_id)
    if profile is not None and profile.default_workspace_id == ws_id:
        personal = next(
            (w for mm, w in await repo.list_memberships(session, user_id) if w.kind == WorkspaceKind.personal), None
        )
        await profiles_repo.update_profile(
            session, profile, {"default_workspace_id": personal.id if personal else None}
        )


def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def invite(session: AsyncSession, ws_id: UUID, actor_id: UUID, body: InvitationCreate) -> InvitationRead:
    me = await _require_membership(session, ws_id, actor_id, "admin")
    ws = await repo.get_workspace(session, ws_id)
    assert ws is not None
    if ws.kind == WorkspaceKind.personal:
        raise Problem(422, "validation_error", "Invalid request", "Personal workspaces cannot have members.")
    if _rank(body.role) >= _rank(me.role):
        raise Problem(403, "insufficient_role", "Insufficient role", "You can only invite roles below your own.")
    email = body.email.lower()
    existing = await repo.list_members(session, ws_id)
    if any(r[4].lower() == email and r[6] == "active" for r in existing):
        raise Problem(409, "conflict", "Already a member", f"{email} is already a member of this workspace.")
    raw = secrets.token_urlsafe(32)
    inv = await inv_repo.create_invitation(session, ws_id, email, body.role, token_hash(raw), actor_id)
    inviter = await profiles_repo.get_profile(session, actor_id)
    link = f"{get_settings().web_url}/invite/{raw}"
    await send_email(
        email,
        f"{inviter.full_name if inviter else 'A teammate'} invited you to {ws.name} on Gravv",
        f"{inviter.full_name if inviter else 'A teammate'} invited you to join the workspace {ws.name} "
        f"as {body.role.value}.\n\nOpen this link to accept:\n{link}\n\nThe link expires in 7 days.",
    )
    return InvitationRead.model_validate(inv)


async def list_invitations(session: AsyncSession, ws_id: UUID, actor_id: UUID) -> list[InvitationRead]:
    await _require_membership(session, ws_id, actor_id, "admin")
    return [InvitationRead.model_validate(i) for i in await inv_repo.list_invitations(session, ws_id)]


async def revoke_invitation(session: AsyncSession, ws_id: UUID, actor_id: UUID, invitation_id: UUID) -> None:
    await _require_membership(session, ws_id, actor_id, "admin")
    inv = await inv_repo.get_invitation(session, ws_id, invitation_id)
    if inv is None:
        raise Problem(404, "not_found", "Invitation not found")
    await inv_repo.revoke_invitation(session, inv)
