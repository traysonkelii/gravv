"""Scoring after interactions, seeded bands, insight rules and actions, analytics summary versus SQL."""

import uuid

import httpx
import pytest
from sqlalchemy import text

from app.db.session import worker_session
from app.scoring.compute import rescore_workspace
from app.scoring.rules import generate_for_workspace
from tests.conftest import AuthAdmin, AuthUser, auth_headers, create_org

SEED_ORG = "00000000-0000-4000-8000-000000000001"
MARTINEZ = "00000000-0000-4000-8000-0000000000a3"
RODRIGUEZ = "00000000-0000-4000-8000-0000000000a2"
JOHNSON = "00000000-0000-4000-8000-0000000000a1"


@pytest.fixture(scope="module")
async def seeded() -> None:
    async with worker_session() as s:
        await rescore_workspace(s, uuid.UUID(SEED_ORG))
        await generate_for_workspace(s, uuid.UUID(SEED_ORG))
        # earlier runs may have acted on this week's insight; the rule dedupes per week
        await s.execute(
            text("update insights set status = 'new' where workspace_id = :ws and kind = 'at_risk' and contact_id = :c"),
            {"ws": SEED_ORG, "c": MARTINEZ},
        )


@pytest.fixture(scope="module")
async def sarah(auth_admin: AuthAdmin) -> AuthUser:
    from tests.conftest import mint_token

    async with worker_session() as s:
        row = (await s.execute(text("select id, email from profiles where email = 'sarah@demo.gravv.local'"))).first()
    assert row is not None, "seed users missing"
    return AuthUser(id=str(row[0]), email=row[1], token=mint_token(auth_admin.settings, str(row[0]), row[1]))


@pytest.fixture(scope="module")
async def priya(auth_admin: AuthAdmin) -> AuthUser:
    from tests.conftest import mint_token

    async with worker_session() as s:
        row = (await s.execute(text("select id, email from profiles where email = 'priya@demo.gravv.local'"))).first()
    assert row is not None
    return AuthUser(id=str(row[0]), email=row[1], token=mint_token(auth_admin.settings, str(row[0]), row[1]))


async def test_seeded_bands(client: httpx.AsyncClient, seeded: None, sarah: AuthUser) -> None:
    h = auth_headers(sarah, SEED_ORG)
    martinez = (await client.get(f"/api/v1/contacts/{MARTINEZ}", headers=h)).json()
    rodriguez = (await client.get(f"/api/v1/contacts/{RODRIGUEZ}", headers=h)).json()
    johnson = (await client.get(f"/api/v1/contacts/{JOHNSON}", headers=h)).json()
    assert martinez["band"] == "drifting" and martinez["status"] == "needs_attention"
    assert rodriguez["band"] == "strong" and rodriguez["gravity_score"] >= 70
    assert johnson["band"] == "strong"
    assert johnson["next_due_at"] is not None
    hist = (await client.get(f"/api/v1/contacts/{JOHNSON}/scores", headers=h, params={"range": "30d"})).json()
    assert hist and hist[-1]["score"] == johnson["gravity_score"]


async def test_new_interaction_rescores_immediately(client: httpx.AsyncClient, auth_admin: AuthAdmin) -> None:
    user = await auth_admin.create_user("score", "Scorer")
    ws = str(await create_org(user, "Score Org"))
    h = auth_headers(user, ws)
    c = (await client.post("/api/v1/contacts", headers=h, json={"first_name": "Fresh", "last_name": "Contact", "cadence_days": 30})).json()
    assert c["gravity_score"] == 0
    r = await client.post(
        "/api/v1/interactions",
        headers=h,
        json={"contact_id": c["id"], "kind": "meeting", "body": "Kickoff.", "sentiment": "positive", "sentiment_score": 0.8},
    )
    assert r.status_code == 201
    after = (await client.get(f"/api/v1/contacts/{c['id']}", headers=h)).json()
    assert after["gravity_score"] > 0 and after["band"] in ("steady", "weak", "strong")
    assert after["next_due_at"] is not None
    # a member logging a note on a teammate's contact also rescores (apply_score is security definer)
    mate = await auth_admin.create_user("score2", "Mate")
    async with worker_session() as s:
        await s.execute(text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"), {"ws": ws, "u": mate.id})
    r = await client.post(
        "/api/v1/interactions", headers=auth_headers(mate, ws), json={"contact_id": c["id"], "kind": "call", "body": "Follow-up call."}
    )
    assert r.status_code == 201, r.text
    again = (await client.get(f"/api/v1/contacts/{c['id']}", headers=h)).json()
    assert again["gravity_score"] >= after["gravity_score"]


async def test_at_risk_insight_and_create_task(client: httpx.AsyncClient, seeded: None, sarah: AuthUser) -> None:
    h = auth_headers(sarah, SEED_ORG)
    insights = (await client.get("/api/v1/insights", headers=h, params={"status": "new"})).json()
    at_risk = [i for i in insights if i["kind"] == "at_risk" and i["contact_id"] == MARTINEZ]
    assert at_risk, [i["title"] for i in insights]
    insight = at_risk[0]
    assert insight["severity"] == "warning" and insight["suggested_action"]["type"] == "create_task"
    assert insight["contact_name"] == "Sarah Martinez"
    r = await client.post(f"/api/v1/insights/{insight['id']}/act", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["task_id"] and r.json()["insight"]["status"] == "acted"
    async with worker_session() as s:
        title = await s.scalar(text("select title from tasks where id = :id"), {"id": r.json()["task_id"]})
    assert title == "Re-engage Sarah Martinez"
    common = [i for i in insights if i["kind"] == "common_ground"]
    assert any("pinball" in i["body"].lower() or "barbecue" in i["body"].lower() for i in common)


async def test_insight_status_and_scope_rules(client: httpx.AsyncClient, seeded: None, sarah: AuthUser, priya: AuthUser) -> None:
    h = auth_headers(sarah, SEED_ORG)
    insights = (await client.get("/api/v1/insights", headers=h, params={"status": "new"})).json()
    one = insights[0]
    r = await client.post(f"/api/v1/insights/{one['id']}/status", headers=h, json={"status": "dismissed"})
    assert r.status_code == 200 and r.json()["status"] == "dismissed"
    # a member sees only their own insights; team scope is manager+
    mine = (await client.get("/api/v1/insights", headers=auth_headers(priya, SEED_ORG))).json()
    assert all(i["user_id"] in (priya.id, None) for i in mine)
    assert (await client.get("/api/v1/insights", headers=auth_headers(priya, SEED_ORG), params={"scope": "team"})).status_code == 403
    team = await client.get("/api/v1/insights", headers=h, params={"scope": "team"})
    assert team.status_code == 200 and len(team.json()) >= len(insights)
    assert (await client.post("/api/v1/insights/generate", headers=auth_headers(priya, SEED_ORG))).status_code == 403


async def test_analytics_summary_matches_sql(client: httpx.AsyncClient, seeded: None, sarah: AuthUser) -> None:
    h = auth_headers(sarah, SEED_ORG)
    r = await client.get("/api/v1/analytics/summary", headers=h, params={"range": "quarter", "scope": "me"})
    assert r.status_code == 200, r.text
    body = r.json()
    async with worker_session() as s:
        expected_count = await s.scalar(
            text(
                "select count(*) from contacts where workspace_id = :ws and owner_user_id = :u and deleted_at is null and status <> 'archived'"
            ),
            {"ws": SEED_ORG, "u": sarah.id},
        )
        expected_avg = await s.scalar(
            text(
                "select round(avg(gravity_score)) from contacts where workspace_id = :ws and owner_user_id = :u and deleted_at is null and status <> 'archived'"
            ),
            {"ws": SEED_ORG, "u": sarah.id},
        )
        expected_pipeline = await s.scalar(
            text(
                "select coalesce(sum(value_cents), 0) from opportunities where workspace_id = :ws and owner_user_id = :u and status = 'open' and deleted_at is null"
            ),
            {"ws": SEED_ORG, "u": sarah.id},
        )
    assert body["contact_count"] == expected_count
    assert body["avg_gravity"] == int(expected_avg)
    assert body["pipeline_value_cents"] == int(expected_pipeline) == 570_000_000
    assert body["open_opportunity_count"] == 2
    assert 0 < body["engagement_rate"] <= 1
    dist = (await client.get("/api/v1/analytics/distribution", headers=h, params={"scope": "me"})).json()
    assert sum(d["count"] for d in dist) == expected_count
    assert {d["band"] for d in dist} == {"strong", "steady", "weak", "drifting"}
    series = (await client.get("/api/v1/analytics/interactions", headers=h, params={"range": "quarter"})).json()
    assert series and all(p["count"] >= 1 for p in series)
    top = (await client.get("/api/v1/analytics/top-contacts", headers=h, params={"scope": "me", "limit": 3})).json()
    assert len(top) == 3 and top[0]["gravity_score"] >= top[1]["gravity_score"]
    team = await client.get("/api/v1/analytics/team", headers=h)
    assert team.status_code == 200 and {m["full_name"] for m in team.json()} >= {"Sarah Chen", "Dan Okafor", "Priya Nair"}


async def test_member_cannot_see_team_analytics(client: httpx.AsyncClient, seeded: None, priya: AuthUser) -> None:
    h = auth_headers(priya, SEED_ORG)
    assert (await client.get("/api/v1/analytics/summary", headers=h, params={"scope": "team"})).status_code == 403
    assert (await client.get("/api/v1/analytics/team", headers=h)).status_code == 403
    assert (await client.get("/api/v1/analytics/summary", headers=h)).status_code == 200


async def test_brief_job_creates_briefing_insight(client: httpx.AsyncClient, seeded: None, sarah: AuthUser) -> None:
    from app.jobs.runner import run_job_now

    h = auth_headers(sarah, SEED_ORG)
    r = await client.post(f"/api/v1/contacts/{JOHNSON}/brief", headers=h)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    if job_id:
        assert await run_job_now(uuid.UUID(job_id)) == "succeeded"
    briefs = (await client.get("/api/v1/insights", headers=h, params={"kind": "briefing", "contact_id": JOHNSON})).json()
    assert briefs and "Where things stand" in briefs[0]["body"]
    assert briefs[0]["evidence"]["structured"]["due_outs"]
