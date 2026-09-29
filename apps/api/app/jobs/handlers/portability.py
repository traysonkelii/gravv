"""export.build (zipped JSON + CSV to the exports bucket) and retention.purge (Section 6.7)."""

import csv
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from app import storage
from app.config import get_settings
from app.db.session import worker_session
from app.email import send_email
from app.jobs.handlers import handler
from app.jobs.queue import Job

TABLES: dict[str, str] = {
    "contacts": "select c.id, c.honorific, c.first_name, c.last_name, c.display_name, c.title, co.name as company, c.emails, c.phones, "
    "c.location, c.relationship_type::text, c.visibility::text, c.status::text, c.tags, c.cadence_days, c.gravity_score, "
    "c.last_interaction_at, c.next_due_at, c.created_at from contacts c left join companies co on co.id = c.company_id "
    "where c.workspace_id = :ws and c.deleted_at is null {contacts_filter} order by c.display_name",
    "companies": "select id, name, domain, industry, type::text, notes, created_at from companies where workspace_id = :ws "
    "and deleted_at is null order by name",
    "interactions": "select i.id, i.contact_id, c.display_name as contact, i.kind::text, i.direction::text, i.occurred_at, i.subject, "
    "i.body, i.summary, i.sentiment::text, i.sentiment_score, i.source::text, i.created_at from interactions i "
    "left join contacts c on c.id = i.contact_id where i.workspace_id = :ws and i.deleted_at is null "
    "{interactions_filter} order by i.occurred_at",
    "facts": "select f.id, f.contact_id, c.display_name as contact, f.category::text, f.content, f.confidence, f.source::text, "
    "f.is_active, f.created_at from contact_facts f join contacts c on c.id = f.contact_id where f.workspace_id = :ws "
    "and c.deleted_at is null {facts_filter} order by c.display_name, f.created_at",
    "tasks": "select t.id, t.contact_id, c.display_name as contact, t.title, t.description, t.due_at, t.status::text, t.priority, "
    "t.completed_at, t.created_at from tasks t left join contacts c on c.id = t.contact_id where t.workspace_id = :ws "
    "{tasks_filter} order by t.created_at",
    "opportunities": "select o.id, o.name, co.name as company, o.value_cents, o.currency, o.stage, o.probability, o.expected_close, "
    "o.status::text, o.notes, o.created_at from opportunities o left join companies co on co.id = o.company_id "
    "where o.workspace_id = :ws and o.deleted_at is null {opportunities_filter} order by o.created_at",
}

CONTRIBUTION_FILTERS = {
    "contacts_filter": "and c.owner_user_id = :uid",
    "interactions_filter": "and i.user_id = :uid",
    "facts_filter": "and f.created_by = :uid",
    "tasks_filter": "and (t.assignee_user_id = :uid or t.created_by = :uid)",
    "opportunities_filter": "and o.owner_user_id = :uid",
}
NO_FILTERS = dict.fromkeys(CONTRIBUTION_FILTERS, "")


def _rows_to_files(name: str, rows: list[dict[str, Any]], zf: zipfile.ZipFile) -> None:
    zf.writestr(f"{name}.json", json.dumps(rows, default=str, indent=1))
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (json.dumps(v, default=str) if isinstance(v, list | dict) else v) for k, v in r.items()})
    zf.writestr(f"{name}.csv", buf.getvalue())


@handler("export.build")
async def export_build(job: Job) -> dict[str, Any]:
    export_id = job.payload["export_id"]
    scope = job.payload["scope"]
    user_id = job.payload["user_id"]
    ws = job.payload["workspace_id"]
    filters = NO_FILTERS if scope in ("personal", "workspace") else CONTRIBUTION_FILTERS
    counts: dict[str, int] = {}
    buf = io.BytesIO()
    # Cross-tenant read as the worker, scoped explicitly by workspace and user (a departed member has no RLS access
    # left, yet the organization owes them their contributions). Listed in docs/DECISIONS.md.
    async with worker_session() as s:
        await s.execute(text("update exports set status = 'running' where id = :id"), {"id": export_id})
        profile = (
            (
                await s.execute(
                    text("select id, email, full_name, role_title, timezone, goals, created_at from profiles where id = :uid"),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "README.txt",
                f"Gravv export\nscope: {scope}\nworkspace: {ws}\nuser: {user_id}\n"
                f"generated: {datetime.now(UTC).isoformat()}\n\nEach table is provided as JSON and CSV.\n",
            )
            if profile:
                zf.writestr("profile.json", json.dumps(dict(profile), default=str, indent=1))
            for name, sql in TABLES.items():
                rows = [dict(r) for r in (await s.execute(text(sql.format(**filters)), {"ws": ws, "uid": user_id})).mappings().all()]
                counts[name] = len(rows)
                _rows_to_files(name, rows, zf)
    path = f"{ws}/{user_id}/{export_id}.zip"
    try:
        await storage.upload_bytes(get_settings().storage_bucket_exports, path, buf.getvalue(), "application/zip")
    except Exception as exc:
        async with worker_session() as s:
            await s.execute(
                text("update exports set status = 'failed', error = :e, finished_at = now() where id = :id"),
                {"id": export_id, "e": str(exc)[:500]},
            )
        raise
    expires = datetime.now(UTC) + timedelta(days=7)
    async with worker_session() as s:
        await s.execute(
            text("update exports set status = 'succeeded', storage_path = :p, expires_at = :x, finished_at = now() where id = :id"),
            {"id": export_id, "p": path, "x": expires},
        )
    notify = job.payload.get("notify_email")
    if notify:
        url = await storage.create_signed_download_url(get_settings().storage_bucket_exports, path, 7 * 24 * 3600)
        await send_email(
            notify, "Your Gravv export is ready", f"Your export of what you contributed is ready. The link works for seven days:\n{url}\n"
        )
    return {"path": path, "counts": counts, "bytes": buf.getbuffer().nbytes}


@handler("retention.purge")
async def retention_purge(job: Job) -> dict[str, Any]:
    """Hard-deletes soft-deleted rows older than 30 days, removes audio 30 days after confirmation unless the
    workspace keeps recordings, and drops expired export files."""
    settings = get_settings()
    purged: dict[str, int] = {}
    async with worker_session() as s:
        for table in ("interactions", "contacts", "companies", "opportunities"):
            res = await s.execute(text(f"delete from {table} where deleted_at < now() - interval '30 days' returning id"))
            purged[table] = len(res.all())
        audio = (
            await s.execute(
                text(
                    "select c.id, c.storage_path from captures c join workspaces w on w.id = c.workspace_id "
                    "where c.kind = 'voice' and c.storage_path is not null and c.status in ('confirmed', 'discarded') "
                    "and c.updated_at < now() - interval '30 days' and coalesce((w.settings->>'retain_audio')::boolean, false) = false "
                    "limit 500"
                )
            )
        ).all()
        expired = (
            await s.execute(text("select id, storage_path from exports where storage_path is not null and expires_at < now() limit 500"))
        ).all()
    for cid, path in audio:
        await storage.delete_object(settings.storage_bucket_voice, path)
        async with worker_session() as s:
            await s.execute(text("update captures set storage_path = null where id = :id"), {"id": cid})
    for eid, path in expired:
        await storage.delete_object(settings.storage_bucket_exports, path)
        async with worker_session() as s:
            await s.execute(text("update exports set storage_path = null where id = :id"), {"id": eid})
    purged["audio"] = len(audio)
    purged["exports"] = len(expired)
    return purged
