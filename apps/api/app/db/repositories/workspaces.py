import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Row, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MembershipStatus, WorkspaceRole
from app.db.models import Membership, Workspace


async def list_memberships(session: AsyncSession, user_id: UUID) -> list[Row[Membership, Workspace]]:
    stmt = (
        select(Membership, Workspace)
        .join(Workspace, Workspace.id == Membership.workspace_id)
        .where(Membership.user_id == user_id)
        .order_by(Workspace.kind, Workspace.name)
    )
    return list((await session.execute(stmt)).all())


async def get_workspace(session: AsyncSession, workspace_id: UUID) -> Workspace | None:
    return await session.get(Workspace, workspace_id)


async def create_organization(session: AsyncSession, name: str, slug: str | None, settings: dict[str, Any]) -> UUID:
    ws_id = await session.scalar(
        text("select create_organization(:name, :slug, cast(:settings as jsonb))"),
        {"name": name, "slug": slug, "settings": json.dumps(settings)},
    )
    assert ws_id is not None
    return UUID(str(ws_id))


async def update_workspace(session: AsyncSession, ws: Workspace, fields: dict[str, Any]) -> Workspace:
    for key, value in fields.items():
        setattr(ws, key, value)
    await session.flush()
    await session.refresh(ws)
    return ws


async def get_membership(session: AsyncSession, workspace_id: UUID, user_id: UUID) -> Membership | None:
    return await session.scalar(
        select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id)
    )


async def list_members(session: AsyncSession, workspace_id: UUID) -> list[Any]:
    rows = await session.execute(
        text(
            "select user_id, full_name, role_title, avatar_path, email, role::text, status::text, joined_at, "
            "departed_at from member_directory where workspace_id = :ws order by role_rank(role) desc, full_name"
        ),
        {"ws": workspace_id},
    )
    return list(rows.all())


async def set_role(session: AsyncSession, membership: Membership, role: WorkspaceRole) -> None:
    membership.role = role
    await session.flush()


async def depart(session: AsyncSession, membership: Membership, grace_days: int = 30) -> None:
    now = datetime.now(UTC)
    membership.status = MembershipStatus.departed
    membership.departed_at = now
    membership.grace_until = now + timedelta(days=grace_days)
    await session.flush()


async def transfer_ownership(
    session: AsyncSession, ws: Workspace, old_owner: Membership, new_owner: Membership
) -> None:
    new_owner.role = WorkspaceRole.owner
    old_owner.role = WorkspaceRole.admin
    ws.owner_user_id = new_owner.user_id
    await session.flush()
