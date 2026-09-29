from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AnonSession, CurrentUser, Session
from app.db.repositories import invitations as inv_repo
from app.domain.workspaces.schemas import AcceptResult, InvitationPeek
from app.domain.workspaces.service import token_hash
from app.errors import Problem

router = APIRouter(prefix="/invitations", tags=["invitations"])


async def _peek(session: AsyncSession, token: str) -> InvitationPeek:
    row = await inv_repo.peek_invitation(session, token_hash(token))
    if row is None:
        raise Problem(404, "not_found", "Invitation not found", "This invitation link is not valid.")
    return InvitationPeek(
        workspace_name=row[0],
        role=row[1],
        inviter_name=row[2],
        email=row[3],
        expires_at=row[4],
        accepted=row[5],
        expired=row[4] < datetime.now(UTC),
    )


@router.get("/{token}", operation_id="invitations_peek", response_model=InvitationPeek)
async def invitations_peek(token: str, session: AnonSession) -> InvitationPeek:
    return await _peek(session, token)


@router.post("/{token}/accept", operation_id="invitations_accept", response_model=AcceptResult)
async def invitations_accept(token: str, ctx: CurrentUser, session: Session) -> AcceptResult:
    ws_id = await inv_repo.accept_invitation(session, token_hash(token))
    return AcceptResult(workspace_id=ws_id)
