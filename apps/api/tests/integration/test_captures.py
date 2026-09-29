import uuid

import httpx
import pytest
from sqlalchemy import text

from app.db.session import worker_session
from app.jobs.runner import run_job_now
from tests.conftest import AuthAdmin, AuthUser, auth_headers, create_org


@pytest.fixture(scope="module")
async def user(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("cap", "Sarah Capture")


@pytest.fixture(scope="module")
async def org(user: AuthUser) -> str:
    return str(await create_org(user, "Capture Org"))


@pytest.fixture(scope="module")
async def johnson(client: httpx.AsyncClient, user: AuthUser, org: str) -> dict[str, object]:
    r = await client.post(
        "/api/v1/contacts",
        headers=auth_headers(user, org),
        json={
            "first_name": "Michael",
            "last_name": "Johnson",
            "honorific": "Col.",
            "title": "Program Director",
            "company_name": "Space Force",
            "cadence_days": 14,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _pending_job_for(capture_id: str) -> uuid.UUID:
    async with worker_session() as s:
        jid = await s.scalar(
            text(
                "select id from jobs where kind = 'capture.extract' and payload->>'capture_id' = :c "
                "order by created_at desc limit 1"
            ),
            {"c": capture_id},
        )
    assert jid is not None, "capture.extract not enqueued"
    return uuid.UUID(str(jid))


async def test_text_capture_to_proposal_to_confirm(
    client: httpx.AsyncClient, user: AuthUser, org: str, johnson: dict[str, object]
) -> None:
    h = auth_headers(user, org)
    key = uuid.uuid4().hex
    r = await client.post(
        "/api/v1/captures/text",
        headers=h,
        json={
            "text": (
                "Met the Colonel, he loves competitive pinball, remind me to call the program officers next Tuesday"
            ),
            "contact_id": johnson["id"],
            "idempotency_key": key,
        },
    )
    assert r.status_code == 202, r.text
    capture = r.json()
    assert capture["status"] == "extracting"
    again = await client.post("/api/v1/captures/text", headers=h, json={"text": "different", "idempotency_key": key})
    assert again.json()["id"] == capture["id"], "idempotency key returns the same capture"

    assert await run_job_now(await _pending_job_for(capture["id"])) == "succeeded"
    r = await client.get(f"/api/v1/captures/{capture['id']}", headers=h)
    body = r.json()
    assert body["status"] == "proposed", body
    proposal = body["proposal"]
    assert proposal["contact_match"]["contact_id"] == johnson["id"]
    assert [f["content"] for f in proposal["facts"]] == ["Competitive pinball"]
    assert [t["title"] for t in proposal["tasks"]] == ["Call the program officers"]
    assert body["provenance"]["provider"] == "fake" and body["provenance"]["prompt_version"] == "extract:v1"

    pending = await client.get("/api/v1/captures", headers=h)
    assert capture["id"] in [c["id"] for c in pending.json()]

    confirm = {
        "contact_id": johnson["id"],
        "interaction": proposal["interaction"],
        "facts": proposal["facts"],
        "tasks": proposal["tasks"],
        "edges": [],
        "create_contacts_for": [],
    }
    r = await client.post(f"/api/v1/captures/{capture['id']}/confirm", headers=h, json=confirm)
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["interaction"]["kind"] == "meeting" and result["interaction"]["ai_status"] == "processed"
    assert len(result["fact_ids"]) == 1 and len(result["task_ids"]) == 1
    assert result["contact"]["open_task_count"] == 1

    facts = await client.get(f"/api/v1/contacts/{johnson['id']}/facts", headers=h)
    assert [f["content"] for f in facts.json()] == ["Competitive pinball"]
    assert facts.json()[0]["source"] == "note"
    tl = await client.get(f"/api/v1/contacts/{johnson['id']}/timeline", headers=h)
    assert tl.json()["items"][0]["kind"] == "meeting"

    # a repeated confirm does not duplicate facts or tasks
    r = await client.post(f"/api/v1/captures/{capture['id']}/confirm", headers=h, json=confirm)
    assert r.status_code == 200
    facts = await client.get(f"/api/v1/contacts/{johnson['id']}/facts", headers=h)
    assert len(facts.json()) == 1
    async with worker_session() as s:
        n = await s.scalar(text("select count(*) from tasks where contact_id = :c"), {"c": johnson["id"]})
        pending_profile = await s.scalar(
            text("select count(*) from jobs where kind = 'profile.synthesize' and payload->>'contact_id' = :c"),
            {"c": johnson["id"]},
        )
    assert n == 1 and pending_profile == 1

    # profile synthesis runs inline and marks the profile fresh
    async with worker_session() as s:
        jid = await s.scalar(
            text(
                "select id from jobs where kind = 'profile.synthesize' and payload->>'contact_id' = :c "
                "order by created_at desc limit 1"
            ),
            {"c": johnson["id"]},
        )
        await s.execute(text("update jobs set run_after = now() + interval '1 hour' where id = :id"), {"id": jid})
    assert await run_job_now(uuid.UUID(str(jid))) == "succeeded"
    prof = await client.get(f"/api/v1/contacts/{johnson['id']}/profile", headers=h)
    assert prof.json()["stale"] is False and "pinball" in prof.json()["summary"].lower()
    assert prof.json()["prompt_version"] == "profile:v1"


async def test_confirm_can_create_mentioned_people(
    client: httpx.AsyncClient, user: AuthUser, org: str, johnson: dict[str, object]
) -> None:
    h = auth_headers(user, org)
    r = await client.post(
        "/api/v1/captures/text",
        headers=h,
        json={
            "text": "Met Johnson; he mentioned Maj. Lisa Park will own the test plan.",
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    capture = r.json()
    await run_job_now(await _pending_job_for(capture["id"]))
    body = (await client.get(f"/api/v1/captures/{capture['id']}", headers=h)).json()
    assert body["proposal"]["mentioned_people"][0]["name"] == "Maj. Lisa Park"
    r = await client.post(
        f"/api/v1/captures/{capture['id']}/confirm",
        headers=h,
        json={
            "contact_id": johnson["id"],
            "interaction": body["proposal"]["interaction"],
            "facts": [],
            "tasks": [],
            "edges": [{"person_a": "Michael Johnson", "person_b": "Lisa Park", "kind": "works_with"}],
            "create_contacts_for": body["proposal"]["mentioned_people"],
        },
    )
    assert r.status_code == 200, r.text
    created = r.json()["created_contact_ids"]
    assert len(created) == 1
    lisa = (await client.get(f"/api/v1/contacts/{created[0]}", headers=h)).json()
    assert lisa["display_name"] == "Lisa Park" and lisa["honorific"] == "Maj."
    async with worker_session() as s:
        edges = await s.scalar(text("select count(*) from contact_edges where workspace_id = :ws"), {"ws": org})
    assert edges == 1


async def test_voice_upload_url_validation_and_missing_object(
    client: httpx.AsyncClient, user: AuthUser, org: str
) -> None:
    h = auth_headers(user, org)
    bad = await client.post(
        "/api/v1/captures/voice/upload-url",
        headers=h,
        json={"content_type": "video/mp4", "size_bytes": 10, "idempotency_key": uuid.uuid4().hex},
    )
    assert bad.status_code == 422
    too_big = await client.post(
        "/api/v1/captures/voice/upload-url",
        headers=h,
        json={"content_type": "audio/webm", "size_bytes": 30 * 1024 * 1024, "idempotency_key": uuid.uuid4().hex},
    )
    assert too_big.status_code == 422
    r = await client.post(
        "/api/v1/captures/voice/upload-url",
        headers=h,
        json={"content_type": "audio/webm", "size_bytes": 1024, "idempotency_key": uuid.uuid4().hex},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["storage_path"].startswith(f"{org}/{user.id}/") and body["storage_path"].endswith(".webm")
    assert body["upload_url"].startswith("http")
    missing = await client.post(f"/api/v1/captures/{body['capture_id']}/uploaded", headers=h, json={})
    assert missing.status_code == 409 and missing.json()["type"].endswith("/upload_missing")


async def test_voice_round_trip_with_fake_transcription(
    client: httpx.AsyncClient, user: AuthUser, org: str, johnson: dict[str, object]
) -> None:
    h = auth_headers(user, org)
    r = await client.post(
        "/api/v1/captures/voice/upload-url",
        headers=h,
        json={
            "content_type": "audio/webm",
            "size_bytes": 200,
            "contact_id": johnson["id"],
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    body = r.json()
    # the fake transcriber returns UTF-8 "audio" verbatim, so a sentence stands in for a recording
    async with httpx.AsyncClient(timeout=30) as up:
        put = await up.put(
            body["upload_url"],
            content=b"Call with Johnson. He dislikes surprise pricing changes.",
            headers=body["headers"],
        )
        assert put.status_code in (200, 201), put.text
    r = await client.post(f"/api/v1/captures/{body['capture_id']}/uploaded", headers=h, json={"duration_seconds": 12})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "transcribing"
    async with worker_session() as s:
        jid = await s.scalar(
            text("select id from jobs where kind = 'capture.transcribe' and payload->>'capture_id' = :c"),
            {"c": body["capture_id"]},
        )
    assert await run_job_now(uuid.UUID(str(jid))) == "succeeded"
    got = (await client.get(f"/api/v1/captures/{body['capture_id']}", headers=h)).json()
    # a live worker may already have extracted; both states prove transcription finished
    assert got["status"] in ("extracting", "proposed") and "surprise pricing" in got["transcript"]
    assert await run_job_now(await _pending_job_for(body["capture_id"])) == "succeeded"
    got = (await client.get(f"/api/v1/captures/{body['capture_id']}", headers=h)).json()
    assert got["status"] == "proposed"
    assert got["proposal"]["facts"][0]["category"] == "dislike"


async def test_discard_and_ownership(
    client: httpx.AsyncClient, user: AuthUser, auth_admin: AuthAdmin, org: str
) -> None:
    h = auth_headers(user, org)
    r = await client.post(
        "/api/v1/captures/text", headers=h, json={"text": "Throwaway note.", "idempotency_key": uuid.uuid4().hex}
    )
    cid = r.json()["id"]
    other = await auth_admin.create_user("cap2", "Other Person")
    assert (await client.get(f"/api/v1/captures/{cid}", headers=auth_headers(other, org))).status_code == 403
    r = await client.post(f"/api/v1/captures/{cid}/discard", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "discarded"
    assert cid not in [c["id"] for c in (await client.get("/api/v1/captures", headers=h)).json()]


async def test_budget_exhaustion_fails_softly(client: httpx.AsyncClient, user: AuthUser, org: str) -> None:
    h = auth_headers(user, org)
    async with worker_session() as s:
        await s.execute(
            text("update workspaces set settings = settings || '{\"ai_daily_token_budget\": 1}'::jsonb where id = :ws"),
            {"ws": org},
        )
        await s.execute(
            text(
                "insert into ai_usage (workspace_id, kind, model, input_tokens, output_tokens) "
                "values (:ws, 'capture.extract', 'fake', 5, 5)"
            ),
            {"ws": org},
        )
    r = await client.post(
        "/api/v1/captures/text", headers=h, json={"text": "Met Johnson again.", "idempotency_key": uuid.uuid4().hex}
    )
    cid = r.json()["id"]
    assert await run_job_now(await _pending_job_for(cid)) == "succeeded"
    got = (await client.get(f"/api/v1/captures/{cid}", headers=h)).json()
    assert got["status"] == "failed" and "budget" in got["error"].lower()
    async with worker_session() as s:
        await s.execute(
            text("update workspaces set settings = settings - 'ai_daily_token_budget' where id = :ws"), {"ws": org}
        )


async def test_interaction_with_extract_creates_review_capture(
    client: httpx.AsyncClient, user: AuthUser, org: str, johnson: dict[str, object]
) -> None:
    h = auth_headers(user, org)
    r = await client.post(
        "/api/v1/interactions",
        headers=h,
        json={
            "contact_id": johnson["id"],
            "kind": "call",
            "body": "Spoke with Johnson, he likes North Carolina barbecue.",
            "extract": True,
        },
    )
    assert r.status_code == 201, r.text
    interaction = r.json()
    pending = (await client.get("/api/v1/captures", headers=h)).json()
    cap = next(c for c in pending if c["interaction_id"] == interaction["id"])
    await run_job_now(await _pending_job_for(cap["id"]))
    body = (await client.get(f"/api/v1/captures/{cap['id']}", headers=h)).json()
    assert body["status"] == "proposed" and body["proposal"]["facts"]
    r = await client.post(
        f"/api/v1/captures/{cap['id']}/confirm",
        headers=h,
        json={
            "contact_id": johnson["id"],
            "interaction": body["proposal"]["interaction"],
            "facts": body["proposal"]["facts"],
            "tasks": [],
            "edges": [],
            "create_contacts_for": [],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["interaction"]["id"] == interaction["id"], "confirm updates the existing note instead of adding one"
    assert r.json()["interaction"]["ai_status"] == "processed"
