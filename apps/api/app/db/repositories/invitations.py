from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import WorkspaceRole
from app.db.models import Invitation


async def create_invitation(
    session: AsyncSession, workspace_id: UUID, email: str, role: WorkspaceRole, token_hash: str, invited_by: UUID
) -> Invitation:
    inv = Invitation(workspace_id=workspace_id, email=email, role=role, token_hash=token_hash, invited_by=invited_by)
    session.add(inv)
    await session.flush()
    await session.refresh(inv)
    return inv


async def list_invitations(session: AsyncSession, workspace_id: UUID) -> list[Invitation]:
    rows = await session.scalars(select(Invitation).where(Invitation.workspace_id == workspace_id).order_by(Invitation.created_at.desc()))
    return list(rows)


async def get_invitation(session: AsyncSession, workspace_id: UUID, invitation_id: UUID) -> Invitation | None:
    return await session.scalar(select(Invitation).where(Invitation.workspace_id == workspace_id, Invitation.id == invitation_id))


async def revoke_invitation(session: AsyncSession, invitation: Invitation) -> None:
    await session.execute(delete(Invitation).where(Invitation.id == invitation.id))


async def peek_invitation(session: AsyncSession, token_hash: str) -> Any | None:
    return (await session.execute(text("select * from peek_invitation(:h)"), {"h": token_hash})).first()


async def accept_invitation(session: AsyncSession, token_hash: str) -> UUID:
    ws_id = await session.scalar(text("select accept_invitation(:h)"), {"h": token_hash})
    assert ws_id is not None
    return UUID(str(ws_id))
