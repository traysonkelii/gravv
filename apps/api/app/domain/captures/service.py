from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.ai.extraction import CaptureExtraction
from app.auth.deps import WorkspaceContext
from app.config import get_settings
from app.db.enums import CaptureStatus, InteractionSource
from app.db.models import Capture
from app.db.repositories import contacts as contacts_repo
from app.db.repositories import facts as facts_repo
from app.db.repositories import interactions as interactions_repo
from app.domain.audit import write_audit
from app.domain.captures.schemas import (
    CaptureConfirm,
    CaptureRead,
    CaptureTextCreate,
    ConfirmResult,
    UploadedRequest,
    VoiceUploadRequest,
    VoiceUploadResponse,
)
from app.domain.contacts import service as contacts_service
from app.domain.contacts.schemas import ContactCreate
from app.domain.interactions.schemas import InteractionRead
from app.errors import Problem
from app.jobs import queue
from app.scoring.compute import rescore_contact

PENDING = ("uploaded", "transcribing", "transcribed", "extracting", "proposed", "failed")


def _read(c: Capture) -> CaptureRead:
    proposal = None
    provenance: dict[str, Any] = {}
    if c.proposal:
        provenance = dict(c.proposal.get("provenance") or {})
        try:
            proposal = CaptureExtraction.model_validate(c.proposal.get("extraction") or {})
        except Exception:
            proposal = None
    return CaptureRead(
        id=c.id,
        workspace_id=c.workspace_id,
        user_id=c.user_id,
        contact_id=c.contact_id,
        kind=c.kind,
        status=c.status,
        transcript=c.transcript,
        raw_text=c.raw_text,
        duration_seconds=c.duration_seconds,
        proposal=proposal,
        provenance=provenance,
        interaction_id=c.interaction_id,
        error=c.error,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


async def _get_own(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, capture_id: UUID) -> Capture:
    c = await session.get(Capture, capture_id)
    if c is None or c.workspace_id != ws.workspace_id or c.user_id != user_id:
        raise Problem(404, "not_found", "Capture not found")
    return c


async def _existing_by_key(session: AsyncSession, user_id: UUID, key: str) -> Capture | None:
    cid = await session.scalar(text("select id from captures where user_id = :u and idempotency_key = :k"), {"u": user_id, "k": key})
    return await session.get(Capture, cid) if cid else None


async def _check_contact(session: AsyncSession, ws: WorkspaceContext, contact_id: UUID | None) -> None:
    if contact_id is not None and await contacts_repo.get_contact(session, ws.workspace_id, contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")


async def create_text(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, body: CaptureTextCreate) -> CaptureRead:
    existing = await _existing_by_key(session, user_id, body.idempotency_key)
    if existing:
        return _read(existing)
    await _check_contact(session, ws, body.contact_id)
    c = Capture(
        workspace_id=ws.workspace_id,
        user_id=user_id,
        contact_id=body.contact_id,
        kind="text",
        raw_text=body.text,
        status=CaptureStatus.extracting,
        idempotency_key=body.idempotency_key,
    )
    session.add(c)
    await session.flush()
    await session.refresh(c)
    await queue.enqueue(
        session,
        "capture.extract",
        {"capture_id": str(c.id)},
        ws.workspace_id,
        priority=1,
        dedupe_key=f"capture.extract:{c.id}",
    )
    return _read(c)


async def create_for_interaction(
    session: AsyncSession, ws: WorkspaceContext, user_id: UUID, interaction_id: UUID, contact_id: UUID, body_text: str
) -> None:
    """interactions_create(extract=true): review facts and tasks for a note that already exists."""
    c = Capture(
        workspace_id=ws.workspace_id,
        user_id=user_id,
        contact_id=contact_id,
        kind="text",
        raw_text=body_text,
        status=CaptureStatus.extracting,
        interaction_id=interaction_id,
        idempotency_key=f"interaction:{interaction_id}",
    )
    session.add(c)
    await session.flush()
    await queue.enqueue(
        session,
        "capture.extract",
        {"capture_id": str(c.id)},
        ws.workspace_id,
        priority=1,
        dedupe_key=f"capture.extract:{c.id}",
    )


async def voice_upload_url(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, body: VoiceUploadRequest) -> VoiceUploadResponse:
    settings = get_settings()
    existing = await _existing_by_key(session, user_id, body.idempotency_key)
    if existing and existing.storage_path:
        signed = await storage.create_signed_upload_url(settings.storage_bucket_voice, existing.storage_path)
        return VoiceUploadResponse(
            capture_id=existing.id,
            upload_url=signed.url,
            token=signed.token,
            storage_path=existing.storage_path,
            headers={"Content-Type": body.content_type, "x-upsert": "true"},
        )
    await _check_contact(session, ws, body.contact_id)
    capture_id = uuid4()
    path = f"{ws.workspace_id}/{user_id}/{capture_id}.{storage.AUDIO_EXTENSIONS[body.content_type]}"
    c = Capture(
        id=capture_id,
        workspace_id=ws.workspace_id,
        user_id=user_id,
        contact_id=body.contact_id,
        kind="voice",
        storage_path=path,
        status=CaptureStatus.uploaded,
        idempotency_key=body.idempotency_key,
    )
    session.add(c)
    await session.flush()
    signed = await storage.create_signed_upload_url(settings.storage_bucket_voice, path)
    return VoiceUploadResponse(
        capture_id=capture_id,
        upload_url=signed.url,
        token=signed.token,
        storage_path=path,
        headers={"Content-Type": body.content_type, "x-upsert": "true"},
    )


async def uploaded(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, capture_id: UUID, body: UploadedRequest) -> CaptureRead:
    c = await _get_own(session, ws, user_id, capture_id)
    if c.kind != "voice" or not c.storage_path:
        raise Problem(409, "conflict", "Not a voice capture")
    if c.status != CaptureStatus.uploaded:
        return _read(c)
    size = await storage.object_size(get_settings().storage_bucket_voice, c.storage_path)
    if size is None:
        raise Problem(
            409,
            "upload_missing",
            "Recording not found",
            "The recording has not arrived in storage. Upload it and try again.",
        )
    if size > storage.MAX_AUDIO_BYTES:
        raise Problem(413, "payload_too_large", "Recording too large", "Recordings are limited to 25 MB.")
    c.status = CaptureStatus.transcribing
    if body.duration_seconds is not None:
        c.duration_seconds = body.duration_seconds
    await session.flush()
    ext = c.storage_path.rsplit(".", 1)[-1]
    mime = next((m for m, e in storage.AUDIO_EXTENSIONS.items() if e == ext), "audio/webm")
    await queue.enqueue(
        session,
        "capture.transcribe",
        {"capture_id": str(c.id), "content_type": mime},
        ws.workspace_id,
        priority=1,
        dedupe_key=f"capture.transcribe:{c.id}",
    )
    await session.refresh(c)
    return _read(c)


async def get(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, capture_id: UUID) -> CaptureRead:
    return _read(await _get_own(session, ws, user_id, capture_id))


async def list_pending(session: AsyncSession, ws: WorkspaceContext, user_id: UUID) -> list[CaptureRead]:
    ids: list[UUID] = list(
        (
            await session.execute(
                text(
                    "select id from captures where workspace_id = :ws and user_id = :u "
                    "and status = any(cast(:st as capture_status[])) order by created_at desc limit 50"
                ),
                {"ws": ws.workspace_id, "u": user_id, "st": list(PENDING)},
            )
        )
        .scalars()
        .all()
    )
    out: list[CaptureRead] = []
    for cid in ids:
        c = await session.get(Capture, cid)
        if c:
            out.append(_read(c))
    return out


async def discard(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, capture_id: UUID) -> CaptureRead:
    c = await _get_own(session, ws, user_id, capture_id)
    if c.status == CaptureStatus.confirmed:
        raise Problem(409, "conflict", "Already saved", "A saved capture cannot be discarded.")
    c.status = CaptureStatus.discarded
    await session.flush()
    await write_audit(session, ws.workspace_id, "capture.discard", "capture", c.id)
    return _read(c)


async def _find_contact_by_name(session: AsyncSession, ws: UUID, name: str) -> UUID | None:
    row = (await session.execute(text("select id from search_contacts(:ws, :q, 1) where rank > 0.3"), {"ws": ws, "q": name})).first()
    return row[0] if row else None


async def confirm(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, capture_id: UUID, body: CaptureConfirm) -> ConfirmResult:
    c = await _get_own(session, ws, user_id, capture_id)
    if c.status == CaptureStatus.confirmed and c.interaction_id:
        # Idempotent: a repeated confirm returns what was created without duplicating anything.
        row = await interactions_repo.get_interaction(session, ws.workspace_id, c.interaction_id)
        contact = await contacts_service.get_contact(session, ws, body.contact_id)
        return ConfirmResult(
            interaction=InteractionRead.model_validate(row),
            contact=contact,
            created_contact_ids=[],
            fact_ids=[],
            task_ids=[],
        )
    if c.status not in (CaptureStatus.proposed, CaptureStatus.failed, CaptureStatus.extracting):
        raise Problem(409, "conflict", "Capture cannot be saved", f"The capture is {c.status.value}.")
    if await contacts_repo.get_contact(session, ws.workspace_id, body.contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")

    source = InteractionSource.voice if c.kind == "voice" else InteractionSource.manual
    extraction_json = (c.proposal or {}).get("extraction")
    fields: dict[str, Any] = {
        "kind": body.interaction.kind,
        "direction": body.interaction.direction,
        "occurred_at": body.interaction.occurred_at or datetime.now(UTC),
        "subject": body.interaction.subject or None,
        "body": body.interaction.body or c.transcript or c.raw_text or "",
        "summary": body.interaction.summary or None,
        "sentiment": body.interaction.sentiment,
        "sentiment_score": body.interaction.sentiment_score,
        "ai_status": "processed",
        "ai_extraction": extraction_json,
    }
    if c.interaction_id:
        row = await interactions_repo.get_interaction(session, ws.workspace_id, c.interaction_id)
        if row is None:
            raise Problem(404, "not_found", "Interaction not found")
        fields.pop("body")
        row = await interactions_repo.update_interaction(session, row, fields)
    else:
        row = await interactions_repo.create_interaction(
            session,
            {
                **fields,
                "workspace_id": ws.workspace_id,
                "contact_id": body.contact_id,
                "user_id": user_id,
                "source": source,
                "metadata_": {"capture_id": str(c.id)},
            },
        )

    fact_ids: list[UUID] = []
    for fact in body.facts:
        if fact.supersedes:
            old = await facts_repo.find_active_duplicate(session, body.contact_id, fact.supersedes)
            if old:
                new = await facts_repo.supersede(
                    session,
                    old,
                    {"category": fact.category, "content": fact.content, "confidence": fact.confidence},
                    user_id,
                )
                fact_ids.append(new.id)
                continue
        if await facts_repo.find_active_duplicate(session, body.contact_id, fact.content):
            continue
        created = await facts_repo.create_fact(
            session,
            {
                "workspace_id": ws.workspace_id,
                "contact_id": body.contact_id,
                "category": fact.category,
                "content": fact.content,
                "confidence": fact.confidence,
                "source": "voice" if c.kind == "voice" else "note",
                "source_interaction_id": row.id,
                "created_by": user_id,
            },
        )
        fact_ids.append(created.id)

    task_ids: list[UUID] = []
    for task in body.tasks:
        target = body.contact_id
        if task.contact_ref:
            target = await _find_contact_by_name(session, ws.workspace_id, task.contact_ref) or body.contact_id
        dup = await session.scalar(
            text(
                "select id from tasks where contact_id = :cid and status = 'open' and lower(title) = lower(:t) "
                "and source_interaction_id = :iid"
            ),
            {"cid": target, "t": task.title, "iid": row.id},
        )
        if dup:
            task_ids.append(dup)
            continue
        tid = await session.scalar(
            text(
                "insert into tasks (workspace_id, assignee_user_id, contact_id, title, due_at, priority, source, "
                "source_interaction_id, created_by) values (:ws, :u, :cid, :t, :due, :p, :src, :iid, :u) returning id"
            ),
            {
                "ws": ws.workspace_id,
                "u": user_id,
                "cid": target,
                "t": task.title,
                "due": task.due_at,
                "p": task.priority,
                "src": "voice" if c.kind == "voice" else "ai",
                "iid": row.id,
            },
        )
        task_ids.append(tid)

    created_contacts: list[UUID] = []
    for person in body.create_contacts_for:
        parts = person.name.replace(",", " ").split()
        honorific = None
        if parts and parts[0].rstrip(".").lower() in {"col", "gen", "dr", "maj", "capt", "mr", "ms", "lt"}:
            honorific = parts.pop(0)
        if not parts:
            continue
        first, last = parts[0], " ".join(parts[1:])
        existing = await _find_contact_by_name(session, ws.workspace_id, f"{first} {last}".strip())
        if existing:
            created_contacts.append(existing)
            continue
        new_contact = await contacts_service.create_contact(
            session,
            ws,
            user_id,
            ContactCreate(first_name=first, last_name=last, honorific=honorific, title=person.title, company_name=person.company),
        )
        created_contacts.append(new_contact.id)

    for edge in body.edges:
        a = await _find_contact_by_name(session, ws.workspace_id, edge.person_a)
        b = await _find_contact_by_name(session, ws.workspace_id, edge.person_b)
        if a and b and a != b:
            lo, hi = sorted([a, b], key=str)
            await session.execute(
                text(
                    "insert into contact_edges (workspace_id, contact_a_id, contact_b_id, kind, source, created_by) "
                    "values (:ws, :a, :b, cast(:k as edge_kind), 'capture', :u) on conflict do nothing"
                ),
                {"ws": ws.workspace_id, "a": lo, "b": hi, "k": edge.kind, "u": user_id},
            )

    c.status = CaptureStatus.confirmed
    c.interaction_id = row.id
    c.contact_id = body.contact_id
    await session.flush()
    await rescore_contact(session, body.contact_id)
    await queue.enqueue(
        session,
        "profile.synthesize",
        {"contact_id": str(body.contact_id)},
        ws.workspace_id,
        priority=3,
        dedupe_key=f"profile.synthesize:{body.contact_id}",
    )
    await write_audit(
        session,
        ws.workspace_id,
        "capture.confirm",
        "capture",
        c.id,
        {"interaction_id": str(row.id), "facts": len(fact_ids), "tasks": len(task_ids)},
    )
    contact = await contacts_service.get_contact(session, ws, body.contact_id)
    return ConfirmResult(
        interaction=InteractionRead.model_validate(row),
        contact=contact,
        created_contact_ids=created_contacts,
        fact_ids=fact_ids,
        task_ids=task_ids,
    )
