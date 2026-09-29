"""capture.transcribe and capture.extract (Section 8.3 steps 4 and 5)."""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app import storage
from app.ai.budget import BudgetExceeded, check_budget, record_usage
from app.ai.extraction import CaptureExtraction
from app.ai.llm import get_llm_client
from app.ai.prompts import render
from app.ai.transcription import get_transcription_client, sniff_audio
from app.config import get_settings
from app.db.session import worker_session
from app.jobs import queue
from app.jobs.handlers import handler
from app.jobs.queue import Job

LOW_RISK = {"preference", "interest", "dislike"}

_LOAD = text(
    "select c.id, c.workspace_id, c.user_id, c.contact_id, c.kind, c.storage_path, c.transcript, c.raw_text, "
    "c.status::text, c.interaction_id, p.full_name, p.role_title, p.timezone, p.email, w.settings "
    "from captures c join profiles p on p.id = c.user_id join workspaces w on w.id = c.workspace_id "
    "where c.id = :id"
)
_SELECTED = text(
    "select c.id, c.honorific, c.display_name, co.name as company, c.title from contacts c "
    "left join companies co on co.id = c.company_id where c.id = :id and c.deleted_at is null"
)
_CANDIDATES = text(
    "select sc.id, c.honorific, sc.display_name, sc.company_name, sc.title "
    "from search_contacts(:ws, :q, 3) sc join contacts c on c.id = sc.id"
)
_AUTO_APPLY = text(
    "insert into contact_facts (workspace_id, contact_id, category, content, confidence, source, created_by) "
    "select :ws, :cid, cast(:cat as fact_category), :content, :conf, 'ai', :uid "
    "where not exists (select 1 from contact_facts where contact_id = :cid and is_active "
    "and lower(btrim(content)) = lower(btrim(:content))) returning id"
)


async def _load_capture(job: Job) -> dict[str, Any]:
    async with worker_session() as s:
        row = (await s.execute(_LOAD, {"id": job.payload["capture_id"]})).mappings().first()
    if row is None:
        raise LookupError(f"capture {job.payload['capture_id']} not found")
    return dict(row)


async def _fail_capture(capture_id: UUID, message: str) -> None:
    async with worker_session() as s:
        await s.execute(
            text("update captures set status = 'failed', error = :e where id = :id"),
            {"id": capture_id, "e": message[:500]},
        )


@handler("capture.transcribe")
async def transcribe(job: Job) -> dict[str, Any]:
    c = await _load_capture(job)
    if c["status"] in ("transcribed", "extracting", "proposed", "confirmed", "discarded"):
        return {"skipped": c["status"]}
    settings = get_settings()
    mime = job.payload.get("content_type", "audio/webm")
    try:
        audio = await storage.download(settings.storage_bucket_voice, c["storage_path"])
        if len(audio) > storage.MAX_AUDIO_BYTES:
            raise ValueError("recording is larger than 25 MB")
        if not sniff_audio(audio, mime) and settings.transcription_provider != "fake":
            raise ValueError(f"file content does not match {mime}")
        transcript = await get_transcription_client(settings).transcribe(audio=audio, mime=mime, language=None)
    except Exception as exc:
        if job.attempts >= job.max_attempts:
            await _fail_capture(c["id"], f"Transcription failed: {exc}")
        raise
    if not transcript.text.strip():
        await _fail_capture(c["id"], "The recording had no speech to transcribe.")
        return {"empty": True}
    async with worker_session() as s:
        await s.execute(
            text(
                "update captures set transcript = :t, duration_seconds = coalesce(duration_seconds, :d), "
                "status = 'extracting' where id = :id"
            ),
            {"id": c["id"], "t": transcript.text, "d": transcript.duration_seconds},
        )
        await queue.enqueue_as_worker(
            s,
            "capture.extract",
            {"capture_id": str(c["id"])},
            c["workspace_id"],
            c["user_id"],
            priority=1,
            dedupe_key=f"capture.extract:{c['id']}",
        )
    return {"chars": len(transcript.text), "provider": transcript.provider}


def _candidate_terms(text_: str) -> list[str]:
    tokens = re.findall(r"\b[A-Z][a-z]{2,}\b", text_)
    stop = {
        "The",
        "This",
        "That",
        "Met",
        "Update",
        "Add",
        "Remind",
        "Book",
        "Call",
        "Send",
        "Next",
        "Today",
        "Yesterday",
    }
    seen: list[str] = []
    for t in tokens:
        if t not in stop and t not in seen:
            seen.append(t)
    return seen[:12]


def _label(honorific: str | None, name: str) -> str:
    return f"{honorific + ' ' if honorific else ''}{name}"


@handler("capture.extract")
async def extract(job: Job) -> dict[str, Any]:
    c = await _load_capture(job)
    if c["status"] in ("proposed", "confirmed", "discarded"):
        return {"skipped": c["status"]}
    capture_text = (c["transcript"] or c["raw_text"] or "").strip()
    if not capture_text:
        await _fail_capture(c["id"], "Nothing to extract from.")
        return {"empty": True}
    user_id, email = c["user_id"], c["email"]

    # Reads run under the practitioner's identity so private contacts of others never reach the prompt.
    async with worker_session(user_id=str(user_id), email=email) as s:
        selected = "none"
        existing_lines: list[str] = []
        if c["contact_id"]:
            row = (await s.execute(_SELECTED, {"id": c["contact_id"]})).mappings().first()
            if row:
                selected = f"{row['id']} | {_label(row['honorific'], row['display_name'])} | {row['company'] or ''} | {row['title'] or ''}"
                facts = (
                    await s.execute(
                        text("select category::text, content from contact_facts where contact_id = :id and is_active"),
                        {"id": c["contact_id"]},
                    )
                ).all()
                existing_lines = [f"- {f[0]}: {f[1]}" for f in facts]
        candidates: dict[str, str] = {}
        for term in _candidate_terms(capture_text):
            rows = (await s.execute(_CANDIDATES, {"ws": c["workspace_id"], "q": term})).all()
            for r in rows:
                candidates[str(r[0])] = f"{r[0]} | {_label(r[1], r[2])} | {r[3] or ''} | {r[4] or ''}"
        if c["contact_id"] and selected != "none":
            candidates.setdefault(str(c["contact_id"]), selected)

    tz = c["timezone"] or "UTC"
    try:
        now = datetime.now(ZoneInfo(tz))
    except Exception:
        now = datetime.now(UTC)
    prompt = render(
        "extract",
        "v1",
        now=now.isoformat(timespec="minutes"),
        timezone=tz,
        user_name=c["full_name"] or "the practitioner",
        user_role=c["role_title"] or "practitioner",
        selected_contact=selected,
        existing_facts="\n".join(existing_lines) or "none",
        candidates="\n".join(candidates.values()) or "none",
        capture=capture_text,
    )
    llm = get_llm_client()
    async with worker_session() as s:
        try:
            await check_budget(s, c["workspace_id"])
        except BudgetExceeded as exc:
            await _fail_capture(c["id"], "The workspace has used its AI budget for today. Try again tomorrow.")
            return {"budget_exceeded": str(exc)}
    try:
        result = await llm.complete_structured(prompt=prompt, schema=CaptureExtraction, max_tokens=4096)
    except Exception as exc:
        if job.attempts >= job.max_attempts:
            await _fail_capture(c["id"], f"Extraction failed: {exc}")
        raise
    extraction = result.value
    if extraction.contact_match and extraction.contact_match.contact_id not in candidates:
        extraction.contact_match = None  # never trust an id the model was not given
    auto_applied: list[str] = []
    provenance: dict[str, Any] = {
        "model": result.model,
        "prompt_version": prompt.id,
        "inputs_hash": hashlib.sha256(prompt.user.encode()).hexdigest()[:16],
        "provider": llm.name,
        "auto_applied_fact_ids": auto_applied,
    }

    settings_json = c["settings"] or {}
    target_contact = (
        extraction.contact_match.contact_id if extraction.contact_match else (str(c["contact_id"]) if c["contact_id"] else None)
    )
    async with worker_session() as s:
        await record_usage(s, c["workspace_id"], user_id, "capture.extract", result.model, result.usage)
        if settings_json.get("auto_apply_low_risk_facts") and target_contact:
            for fact in extraction.facts:
                if fact.category.value in LOW_RISK and fact.confidence >= 0.9 and not fact.supersedes:
                    fid = await s.scalar(
                        _AUTO_APPLY,
                        {
                            "ws": c["workspace_id"],
                            "cid": target_contact,
                            "cat": fact.category.value,
                            "content": fact.content,
                            "conf": fact.confidence,
                            "uid": user_id,
                        },
                    )
                    if fid:
                        auto_applied.append(str(fid))
        payload = {"extraction": extraction.model_dump(mode="json"), "provenance": provenance}
        await s.execute(
            text("update captures set proposal = cast(:p as jsonb), status = 'proposed', error = null where id = :id"),
            {"id": c["id"], "p": json.dumps(payload)},
        )
    return {
        "facts": len(extraction.facts),
        "tasks": len(extraction.tasks),
        "matched": bool(extraction.contact_match),
        "tokens": result.usage.total,
    }
