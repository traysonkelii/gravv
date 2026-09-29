import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text

from app.db.session import worker_session
from tests.conftest import AuthAdmin, AuthUser, auth_headers, create_org, mint_token

SEED_ORG = "00000000-0000-4000-8000-000000000001"
JOHNSON = "00000000-0000-4000-8000-0000000000a1"
CHEN = "00000000-0000-4000-8000-0000000000a5"
WILLIAMS = "00000000-0000-4000-8000-0000000000a7"
NASA = "00000000-0000-4000-8000-0000000000c6"


@pytest.fixture(scope="module")
async def sarah(auth_admin: AuthAdmin) -> AuthUser:
    async with worker_session() as s:
        row = (await s.execute(text("select id, email from profiles where email = 'sarah@demo.gravv.local'"))).first()
    assert row is not None
    return AuthUser(id=str(row[0]), email=row[1], token=mint_token(auth_admin.settings, str(row[0]), row[1]))


@pytest.fixture(scope="module")
async def user(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("tasks", "Tara Tasks")


@pytest.fixture(scope="module")
async def org(user: AuthUser) -> str:
    return str(await create_org(user, "Tasks Org"))


@pytest.fixture(scope="module")
async def contact(client: httpx.AsyncClient, user: AuthUser, org: str) -> dict[str, object]:
    r = await client.post(
        "/api/v1/contacts", headers=auth_headers(user, org), json={"first_name": "Task", "last_name": "Target", "cadence_days": 30}
    )
    assert r.status_code == 201
    return r.json()  # type: ignore[no-any-return]


async def test_task_lifecycle(client: httpx.AsyncClient, user: AuthUser, org: str, contact: dict[str, object]) -> None:
    h = auth_headers(user, org)
    due = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    r = await client.post(
        "/api/v1/tasks", headers=h, json={"title": "Send the deck", "due_at": due, "contact_id": contact["id"], "priority": 1}
    )
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["assignee_user_id"] == user.id and task["contact_name"] == "Task Target" and task["status"] == "open"
    c = (await client.get(f"/api/v1/contacts/{contact['id']}", headers=h)).json()
    assert c["open_task_count"] == 1 and c["next_due_at"] is not None

    listing = await client.get("/api/v1/tasks", headers=h, params={"status": "open", "assignee": "me"})
    assert [t["id"] for t in listing.json()["items"]] == [task["id"]]
    until = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    r = await client.post(f"/api/v1/tasks/{task['id']}/snooze", headers=h, json={"until": until})
    assert r.status_code == 200 and r.json()["status"] == "snoozed"
    bad = await client.post(f"/api/v1/tasks/{task['id']}/snooze", headers=h, json={"until": "2020-01-01T00:00:00Z"})
    assert bad.status_code == 422
    r = await client.patch(f"/api/v1/tasks/{task['id']}", headers=h, json={"title": "Send the revised deck", "status": "open"})
    assert r.json()["title"] == "Send the revised deck" and r.json()["status"] == "open"
    r = await client.post(f"/api/v1/tasks/{task['id']}/complete", headers=h)
    assert r.json()["status"] == "done" and r.json()["completed_at"]
    c = (await client.get(f"/api/v1/contacts/{contact['id']}", headers=h)).json()
    assert c["open_task_count"] == 0
    tl = (await client.get(f"/api/v1/contacts/{contact['id']}/timeline", headers=h, params={"kinds": ["task"]})).json()
    assert tl["items"] and tl["items"][0]["title"] == "Send the revised deck"


async def test_task_validation_and_roles(client: httpx.AsyncClient, user: AuthUser, auth_admin: AuthAdmin, org: str) -> None:
    h = auth_headers(user, org)
    assert (await client.post("/api/v1/tasks", headers=h, json={"title": ""})).status_code == 422
    assert (await client.post("/api/v1/tasks", headers=h, json={"title": "x", "contact_id": str(uuid.uuid4())})).status_code == 404
    viewer = await auth_admin.create_user("tviewer", "Vera Viewer")
    async with worker_session() as s:
        await s.execute(
            text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'viewer')"), {"ws": org, "u": viewer.id}
        )
    assert (await client.post("/api/v1/tasks", headers=auth_headers(viewer, org), json={"title": "Nope"})).status_code == 403
    assert (await client.get("/api/v1/tasks", headers=auth_headers(viewer, org))).status_code == 200


async def test_opportunity_lifecycle(client: httpx.AsyncClient, user: AuthUser, org: str, contact: dict[str, object]) -> None:
    h = auth_headers(user, org)
    r = await client.post(
        "/api/v1/opportunities",
        headers=h,
        json={"name": "Radar recompete", "company_name": "U.S. Army", "value_cents": 120000000, "stage": "proposal", "probability": 40},
    )
    assert r.status_code == 201, r.text
    opp = r.json()
    assert opp["company"]["name"] == "U.S. Army" and opp["value_cents"] == 120000000 and opp["contacts"] == []
    r = await client.put(f"/api/v1/opportunities/{opp['id']}/contacts/{contact['id']}", headers=h, json={"role": "decision_maker"})
    assert r.status_code == 200 and r.json()["contacts"][0]["role"] == "decision_maker"
    c = (await client.get(f"/api/v1/contacts/{contact['id']}", headers=h)).json()
    assert c["open_opportunity_value_cents"] == 120000000
    summary = (await client.get("/api/v1/analytics/summary", headers=h, params={"range": "month"})).json()
    assert summary["pipeline_value_cents"] == 120000000 and summary["open_opportunity_count"] == 1
    r = await client.patch(f"/api/v1/opportunities/{opp['id']}", headers=h, json={"status": "won", "value_cents": 130000000})
    assert r.json()["status"] == "won"
    summary = (await client.get("/api/v1/analytics/summary", headers=h, params={"range": "month"})).json()
    assert summary["pipeline_value_cents"] == 0
    r = await client.delete(f"/api/v1/opportunities/{opp['id']}/contacts/{contact['id']}", headers=h)
    assert r.json()["contacts"] == []
    listing = (await client.get("/api/v1/opportunities", headers=h, params={"status": "won"})).json()
    assert [o["id"] for o in listing["items"]] == [opp["id"]]
    assert (await client.delete(f"/api/v1/opportunities/{opp['id']}", headers=h)).status_code == 204
    assert (await client.get(f"/api/v1/opportunities/{opp['id']}", headers=h)).status_code == 404


async def test_edges_canonical_and_visible(client: httpx.AsyncClient, user: AuthUser, org: str, contact: dict[str, object]) -> None:
    h = auth_headers(user, org)
    other = (await client.post("/api/v1/contacts", headers=h, json={"first_name": "Edge", "last_name": "Other"})).json()
    r = await client.post(
        f"/api/v1/contacts/{contact['id']}/edges", headers=h, json={"other_contact_id": other["id"], "kind": "works_with", "strength": 70}
    )
    assert r.status_code == 201, r.text
    edge = r.json()
    assert edge["other_display_name"] == "Edge Other" and edge["kind"] == "works_with"
    again = await client.post(f"/api/v1/contacts/{other['id']}/edges", headers=h, json={"other_contact_id": contact["id"], "strength": 80})
    assert again.status_code == 201 and again.json()["id"] == edge["id"], "reverse order upserts the same canonical edge"
    assert again.json()["strength"] == 80
    self_link = await client.post(f"/api/v1/contacts/{contact['id']}/edges", headers=h, json={"other_contact_id": contact["id"]})
    assert self_link.status_code == 422
    graph = (await client.get("/api/v1/network/graph", headers=h)).json()
    ids = {n["id"] for n in graph["nodes"]}
    assert "me" in ids and contact["id"] in ids and other["id"] in ids
    assert any(e["source"] == "me" and e["target"] == contact["id"] for e in graph["edges"])
    assert any({e["source"], e["target"]} == {contact["id"], other["id"]} for e in graph["edges"])
    assert (await client.delete(f"/api/v1/edges/{edge['id']}", headers=h)).status_code == 204
    assert (await client.get(f"/api/v1/contacts/{contact['id']}/edges", headers=h)).json() == []


async def test_seeded_graph_and_paths(client: httpx.AsyncClient, sarah: AuthUser) -> None:
    h = auth_headers(sarah, SEED_ORG)
    graph = (await client.get("/api/v1/network/graph", headers=h)).json()
    contacts = [n for n in graph["nodes"] if n["kind"] == "contact"]
    seeded_ids = {f"00000000-0000-4000-8000-0000000000a{x}" for x in "123456789a"}
    assert seeded_ids <= {n["id"] for n in contacts}  # e2e runs add more contacts to the shared seed workspace
    assert graph["nodes"][0]["kind"] == "me" and graph["nodes"][0]["display_name"] == "Sarah Chen"
    johnson = next(n for n in contacts if n["id"] == JOHNSON)
    assert johnson["initials"] == "MJ" and johnson["company"] == "Space Force" and johnson["deal_value_cents"] == 250000000
    edges = (await client.get(f"/api/v1/contacts/{JOHNSON}/edges", headers=h)).json()
    assert {e["other_display_name"] for e in edges} == {"James Chen", "Patricia Williams"}
    paths = (await client.get("/api/v1/network/paths", headers=h, params={"from": "me", "to": NASA})).json()
    assert paths["to_ids"] == [CHEN]
    assert paths["paths"][0]["nodes"] == ["me", CHEN] and paths["paths"][0]["hops"] == 1
    via = (await client.get("/api/v1/network/paths", headers=h, params={"from": JOHNSON, "to": WILLIAMS})).json()
    assert via["paths"][0]["nodes"] == [JOHNSON, WILLIAMS]
    filtered = (await client.get("/api/v1/network/graph", headers=h, params={"industry": "government"})).json()
    assert all(n["industry"] == "government" for n in filtered["nodes"] if n["kind"] == "contact")
    strong_only = (await client.get("/api/v1/network/graph", headers=h, params={"min_score": 70})).json()
    assert all(n["gravity_score"] >= 70 for n in strong_only["nodes"] if n["kind"] == "contact")
    assert (await client.get("/api/v1/network/paths", headers=h, params={"to": "nobody"})).status_code == 404
