from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.auth.deps import WorkspaceContext
from app.config import get_settings
from app.db.enums import WorkspaceKind
from app.db.repositories import workspaces as workspaces_repo
from app.domain.audit import write_audit
from app.domain.exports.schemas import ExportAccepted, ExportRead
from app.errors import Problem
from app.jobs import queue


async def request_export(
    session: AsyncSession,
    user_id: UUID,
    scope: str,
    workspace_id: UUID | None,
    notify_email: str | None = None,
    for_user_id: UUID | None = None,
) -> ExportAccepted:
    """personal: the caller's personal workspace. my_contributions: the given (or current) organization.
    workspace: the whole organization, admins only. Admins may request my_contributions for a departing member."""
    target_user = for_user_id or user_id
    if scope == "personal":
        rows = await workspaces_repo.list_memberships(session, user_id)
        personal = next((w for _m, w in rows if w.kind == WorkspaceKind.personal), None)
        if personal is None:
            raise Problem(404, "not_found", "Personal workspace not found")
        workspace_id = personal.id
    if workspace_id is None:
        raise Problem(422, "validation_error", "Invalid request", "A workspace is required for this export scope.")
    export_id = await session.scalar(
        text("select create_export(:ws, :uid, :scope)"), {"ws": workspace_id, "uid": target_user, "scope": scope}
    )
    assert export_id is not None
    payload: dict[str, Any] = {"export_id": str(export_id), "scope": scope, "user_id": str(target_user), "workspace_id": str(workspace_id)}
    if notify_email:
        payload["notify_email"] = notify_email
    job_id = await queue.enqueue(session, "export.build", payload, workspace_id, priority=4, dedupe_key=f"export.build:{export_id}")
    await write_audit(session, workspace_id, "export.request", "export", export_id, {"scope": scope, "for": str(target_user)})
    return ExportAccepted(export_id=export_id, job_id=job_id)


async def get_export(session: AsyncSession, export_id: UUID) -> ExportRead:
    r = (
        (
            await session.execute(
                text(
                    "select id, workspace_id, user_id, scope, status::text, storage_path, expires_at, error, created_at, finished_at "
                    "from exports where id = :id"
                ),
                {"id": export_id},
            )
        )
        .mappings()
        .first()
    )
    if r is None:
        raise Problem(404, "not_found", "Export not found")
    url = None
    if r["status"] == "succeeded" and r["storage_path"]:
        url = await storage.create_signed_download_url(get_settings().storage_bucket_exports, r["storage_path"], 300)
    return ExportRead(
        id=r["id"],
        workspace_id=r["workspace_id"],
        user_id=r["user_id"],
        scope=r["scope"],
        status=r["status"],
        download_url=url,
        expires_at=r["expires_at"],
        error=r["error"],
        created_at=r["created_at"],
        finished_at=r["finished_at"],
    )


async def list_mine(session: AsyncSession) -> list[ExportRead]:
    rows = await session.execute(text("select id from exports where user_id = auth.uid() order by created_at desc limit 20"))
    return [await get_export(session, r[0]) for r in rows.all()]


async def request_workspace_export(session: AsyncSession, ws: WorkspaceContext, user_id: UUID) -> ExportAccepted:
    if not ws.at_least("admin"):
        raise Problem(403, "insufficient_role", "Insufficient role", "Workspace exports require the admin role.")
    return await request_export(session, user_id, "workspace", ws.workspace_id)
