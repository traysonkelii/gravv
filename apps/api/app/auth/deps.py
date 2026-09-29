import json
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import AuthContext, verify_token
from app.db.session import api_session_factory
from app.errors import Problem

_bearer = HTTPBearer(auto_error=False)

ROLE_RANK = {"viewer": 1, "member": 2, "manager": 3, "admin": 4, "owner": 5}


@dataclass(frozen=True)
class WorkspaceContext:
    workspace_id: UUID
    role: str
    settings: dict[str, Any]

    def at_least(self, min_role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[min_role]


async def current_user(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise Problem(401, "unauthenticated", "Unauthenticated", "Provide a bearer token.")
    ctx = verify_token(credentials.credentials)
    request.state.auth = ctx
    structlog.contextvars.bind_contextvars(user_id=ctx.user_id)
    return ctx


CurrentUser = Annotated[AuthContext, Depends(current_user)]


async def bind_identity(session: AsyncSession, ctx: AuthContext | None) -> None:
    """First statements of every transaction: assume the PostgREST role and publish the JWT claims."""
    if ctx is None:
        await session.execute(text("set local role anon"))
        return
    await session.execute(text("set local role authenticated"))
    claims = {
        "sub": ctx.user_id,
        "role": "authenticated",
        "email": ctx.email,
        "aal": ctx.aal,
        "session_id": ctx.session_id,
    }
    await session.execute(text("select set_config('request.jwt.claims', :claims, true)"), {"claims": json.dumps(claims)})


async def get_session(ctx: CurrentUser) -> AsyncIterator[AsyncSession]:
    """One RLS-bound transaction per request. Commits on success, rolls back on any exception."""
    async with api_session_factory()() as session, session.begin():
        await bind_identity(session, ctx)
        yield session


async def get_anon_session() -> AsyncIterator[AsyncSession]:
    async with api_session_factory()() as session, session.begin():
        await bind_identity(session, None)
        yield session


Session = Annotated[AsyncSession, Depends(get_session)]
AnonSession = Annotated[AsyncSession, Depends(get_anon_session)]


async def current_workspace(
    ctx: CurrentUser,
    session: Session,
    x_workspace_id: Annotated[str | None, Header()] = None,
) -> WorkspaceContext:
    ws_id: UUID | None = None
    if x_workspace_id:
        try:
            ws_id = UUID(x_workspace_id)
        except ValueError as exc:
            raise Problem(400, "bad_request", "Bad request", "X-Workspace-Id is not a UUID.") from exc
    else:
        row = await session.execute(text("select default_workspace_id from profiles where id = auth.uid()"))
        ws_id = row.scalar_one_or_none()
    if ws_id is None:
        raise Problem(403, "not_a_member", "No workspace", "Select a workspace with the X-Workspace-Id header.")
    row = await session.execute(
        text(
            "select m.role::text, w.settings from memberships m join workspaces w on w.id = m.workspace_id "
            "where m.workspace_id = :ws and m.user_id = auth.uid() and m.status = 'active'"
        ),
        {"ws": ws_id},
    )
    found = row.first()
    if found is None:
        raise Problem(403, "not_a_member", "Not a member", "You are not an active member of this workspace.")
    structlog.contextvars.bind_contextvars(workspace_id=str(ws_id))
    return WorkspaceContext(workspace_id=ws_id, role=found[0], settings=found[1] or {})


Workspace = Annotated[WorkspaceContext, Depends(current_workspace)]


def require_role(min_role: str) -> Callable[..., Coroutine[Any, Any, WorkspaceContext]]:
    async def _dep(ws: Workspace) -> WorkspaceContext:
        if not ws.at_least(min_role):
            raise Problem(
                403,
                "insufficient_role",
                "Insufficient role",
                f"This action requires the {min_role} role or higher.",
            )
        return ws

    return _dep


def require_mfa() -> Callable[..., Coroutine[Any, Any, None]]:
    async def _dep(ctx: CurrentUser, ws: Workspace) -> None:
        if ws.settings.get("require_mfa") and ctx.aal != "aal2":
            raise Problem(
                403,
                "mfa_required",
                "Multi-factor authentication required",
                "This workspace requires a second factor for this action.",
            )

    return _dep
