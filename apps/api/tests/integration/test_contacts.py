import uuid
from typing import Any

import httpx
import pytest

from tests.conftest import AuthAdmin, AuthUser, auth_headers, create_org


@pytest.fixture(scope="module")
async def owner(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("cowner", "Casey Owner")


@pytest.fixture(scope="module")
async def teammate(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("cmate", "Tess Teammate")


@pytest.fixture(scope="module")
async def viewer(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("cviewer", "Vic Viewer")


@pytest.fixture(scope="module")
async def org(client: httpx.AsyncClient, owner: AuthUser, teammate: AuthUser, viewer: AuthUser) -> str:
    ws = str(await create_org(owner, "Contacts Org"))
    for u, role in ((teammate, "member"), (viewer, "viewer")):
        r = await client.post(
            f"/api/v1/workspaces/{ws}/invitations", headers=auth_headers(owner), json={"email": u.email, "role": role}
        )
        assert r.status_code == 201, r.text
    from sqlalchemy import text

    from tests.conftest import rls_session

    async with rls_session(owner) as s:
        await s.execute(text("update memberships set status='active' where workspace_id=:ws"), {"ws": ws})
        for u, role in ((teammate, "member"), (viewer, "viewer")):
            await s.execute(
                text(
                    "insert into memberships (workspace_id, user_id, role) values (:ws, :u, :r) on conflict do nothing"
                ),
                {"ws": ws, "u": u.id, "r": role},
            )
    return ws


async def _create(client: httpx.AsyncClient, user: AuthUser, ws: str, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "first_name": "Michael",
        "last_name": "Johnson",
        "honorific": "Col.",
        "title": "Program Director",
        "company_name": "Space Force",
        "emails": ["michael.johnson@spaceforce.mil"],
        "tags": ["satellite"],
        "relationship_type": "government",
        "cadence_days": 14,
    }
    body.update(over)
    r = await client.post("/api/v1/contacts", headers=auth_headers(user, ws), json=body)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_create_contact_creates_company_and_profile(client: httpx.AsyncClient, owner: AuthUser, org: str) -> None:
    c = await _create(client, owner, org)
    assert c["display_name"] == "Michael Johnson"
    assert c["company"]["name"] == "Space Force"
    assert c["band"] == "weak" and c["gravity_score"] == 0
    assert c["visibility"] == "team"
    assert c["profile"]["stale"] is True
    # same company name links, does not duplicate
    d = await _create(client, owner, org, first_name="Patricia", last_name="Williams", honorific="Gen.")
    assert d["company"]["id"] == c["company"]["id"]
    companies = await client.get("/api/v1/companies", headers=auth_headers(owner, org))
    assert [x["name"] for x in companies.json()["items"]] == ["Space Force"]


async def test_validation_limits(client: httpx.AsyncClient, owner: AuthUser, org: str) -> None:
    r = await client.post("/api/v1/contacts", headers=auth_headers(owner, org), json={"first_name": ""})
    assert r.status_code == 422
    r = await client.post(
        "/api/v1/contacts", headers=auth_headers(owner, org), json={"first_name": "X", "emails": ["not-an-email"]}
    )
    assert r.status_code == 422
    r = await client.post("/api/v1/contacts", headers=auth_headers(owner, org), json={"first_name": "X", "bogus": 1})
    assert r.status_code == 422


async def test_viewer_cannot_create(client: httpx.AsyncClient, viewer: AuthUser, org: str) -> None:
    r = await client.post("/api/v1/contacts", headers=auth_headers(viewer, org), json={"first_name": "Nope"})
    assert r.status_code == 403
    assert r.json()["type"].endswith("/insufficient_role")


async def test_private_contact_invisible_to_teammate(
    client: httpx.AsyncClient, owner: AuthUser, teammate: AuthUser, org: str
) -> None:
    private = await _create(
        client, owner, org, first_name="Secret", last_name="Source", visibility="private", company_name=None
    )
    mine = await client.get("/api/v1/contacts", headers=auth_headers(owner, org), params={"q": "Secret"})
    assert [c["id"] for c in mine.json()["items"]] == [private["id"]]
    theirs = await client.get("/api/v1/contacts", headers=auth_headers(teammate, org), params={"q": "Secret"})
    assert theirs.json()["items"] == []
    assert (
        await client.get(f"/api/v1/contacts/{private['id']}", headers=auth_headers(teammate, org))
    ).status_code == 404
    # nor through facts or timeline
    assert (
        await client.get(f"/api/v1/contacts/{private['id']}/facts", headers=auth_headers(teammate, org))
    ).status_code == 404


async def test_list_filters_sort_and_cursor(client: httpx.AsyncClient, owner: AuthUser, org: str) -> None:
    for i in range(3):
        await _create(
            client,
            owner,
            org,
            first_name=f"Page{i}",
            last_name="Test",
            company_name="Boeing",
            tags=["paging"],
            relationship_type="client",
        )
    h = auth_headers(owner, org)
    first = await client.get("/api/v1/contacts", headers=h, params={"tag": "paging", "sort": "name", "limit": 2})
    assert first.status_code == 200, first.text
    assert [c["display_name"] for c in first.json()["items"]] == ["Page0 Test", "Page1 Test"]
    assert first.json()["next_cursor"]
    second = await client.get(
        "/api/v1/contacts",
        headers=h,
        params={"tag": "paging", "sort": "name", "limit": 2, "cursor": first.json()["next_cursor"]},
    )
    assert [c["display_name"] for c in second.json()["items"]] == ["Page2 Test"]
    assert second.json()["next_cursor"] is None
    by_type = await client.get("/api/v1/contacts", headers=h, params={"relationship_type": "client", "tag": "paging"})
    assert len(by_type.json()["items"]) == 3
    bad = await client.get("/api/v1/contacts", headers=h, params={"cursor": "!!!"})
    assert bad.status_code == 400
    wrong_sort = await client.get(
        "/api/v1/contacts", headers=h, params={"sort": "gravity", "cursor": first.json()["next_cursor"]}
    )
    assert wrong_sort.status_code == 400
    fuzzy = await client.get("/api/v1/contacts", headers=h, params={"q": "page0 tset"})
    assert any(c["display_name"] == "Page0 Test" for c in fuzzy.json()["items"])


async def test_update_rules(client: httpx.AsyncClient, owner: AuthUser, teammate: AuthUser, org: str) -> None:
    c = await _create(client, owner, org, first_name="Emily", last_name="Rodriguez", company_name="Boeing")
    r = await client.patch(f"/api/v1/contacts/{c['id']}", headers=auth_headers(teammate, org), json={"title": "Hijack"})
    assert r.status_code == 403  # member editing someone else's contact
    r = await client.patch(
        f"/api/v1/contacts/{c['id']}",
        headers=auth_headers(owner, org),
        json={"title": "Senior Contract Manager", "company_name": "Boeing Defense", "tags": ["contracts"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Senior Contract Manager"
    assert r.json()["company"]["name"] == "Boeing Defense"
    r = await client.delete(f"/api/v1/contacts/{c['id']}", headers=auth_headers(teammate, org))
    assert r.status_code == 403
    r = await client.delete(f"/api/v1/contacts/{c['id']}", headers=auth_headers(owner, org))
    assert r.status_code == 204
    assert (await client.get(f"/api/v1/contacts/{c['id']}", headers=auth_headers(owner, org))).status_code == 404


async def test_facts_supersede_and_archive(client: httpx.AsyncClient, owner: AuthUser, org: str) -> None:
    c = await _create(client, owner, org, first_name="Facts", last_name="Person", company_name=None)
    h = auth_headers(owner, org)
    r = await client.post(
        f"/api/v1/contacts/{c['id']}/facts", headers=h, json={"category": "preference", "content": "Drinks Diet Coke"}
    )
    assert r.status_code == 201, r.text
    fact = r.json()
    dup = await client.post(
        f"/api/v1/contacts/{c['id']}/facts", headers=h, json={"category": "preference", "content": "drinks diet coke "}
    )
    assert dup.status_code == 409
    r = await client.patch(f"/api/v1/facts/{fact['id']}", headers=h, json={"content": "Drinks Diet Coke, never coffee"})
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["id"] != fact["id"] and new["content"].endswith("never coffee")
    active = await client.get(f"/api/v1/contacts/{c['id']}/facts", headers=h)
    assert [f["id"] for f in active.json()] == [new["id"]]
    everything = await client.get(f"/api/v1/contacts/{c['id']}/facts", headers=h, params={"include_inactive": "true"})
    old = next(f for f in everything.json() if f["id"] == fact["id"])
    assert old["is_active"] is False and old["superseded_by"] == new["id"]
    assert (await client.delete(f"/api/v1/facts/{new['id']}", headers=h)).status_code == 204
    assert (await client.get(f"/api/v1/contacts/{c['id']}/facts", headers=h)).json() == []


async def test_interactions_and_timeline(
    client: httpx.AsyncClient, owner: AuthUser, teammate: AuthUser, org: str
) -> None:
    c = await _create(client, owner, org, first_name="Timeline", last_name="Person", company_name=None)
    h = auth_headers(owner, org)
    r = await client.post(
        "/api/v1/interactions",
        headers=h,
        json={
            "contact_id": c["id"],
            "kind": "meeting",
            "subject": "Phase 2 review",
            "body": "Reviewed the schedule. He wants a revised cost sheet before the 15th.",
            "sentiment": "positive",
            "sentiment_score": 0.6,
            "occurred_at": "2026-09-20T14:30:00Z",
        },
    )
    assert r.status_code == 201, r.text
    meeting = r.json()
    r = await client.post(
        "/api/v1/interactions",
        headers=auth_headers(teammate, org),
        json={
            "contact_id": c["id"],
            "kind": "email",
            "body": "Sent the cost sheet.",
            "occurred_at": "2026-09-22T09:00:00Z",
        },
    )
    assert r.status_code == 201, r.text  # members may log notes on team contacts
    detail = await client.get(f"/api/v1/contacts/{c['id']}", headers=h)
    assert detail.json()["last_interaction"]["kind"] == "email"
    tl = await client.get(f"/api/v1/contacts/{c['id']}/timeline", headers=h)
    assert [e["kind"] for e in tl.json()["items"]] == ["email", "meeting"]
    assert tl.json()["items"][1]["title"] == "Phase 2 review"
    only_meetings = await client.get(f"/api/v1/contacts/{c['id']}/timeline", headers=h, params={"kinds": ["meeting"]})
    assert [e["kind"] for e in only_meetings.json()["items"]] == ["meeting"]
    # teammate cannot edit the owner's note; owner can
    assert (
        await client.patch(
            f"/api/v1/interactions/{meeting['id']}", headers=auth_headers(teammate, org), json={"subject": "x"}
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/interactions/{meeting['id']}", headers=h, json={"subject": "Phase 2 schedule review"}
        )
    ).status_code == 200
    listing = await client.get("/api/v1/interactions", headers=h, params={"contact_id": c["id"], "limit": 1})
    assert len(listing.json()["items"]) == 1 and listing.json()["next_cursor"]
    assert (await client.delete(f"/api/v1/interactions/{meeting['id']}", headers=h)).status_code == 204
    detail = await client.get(f"/api/v1/contacts/{c['id']}", headers=h)
    assert detail.json()["last_interaction"]["kind"] == "email"


async def test_share_to_org_and_copy_back(
    client: httpx.AsyncClient, owner: AuthUser, teammate: AuthUser, org: str
) -> None:
    me = await client.get("/api/v1/me", headers=auth_headers(teammate))
    personal = next(m["workspace_id"] for m in me.json()["memberships"] if m["kind"] == "personal")
    p = await _create(
        client, teammate, personal, first_name="Maya", last_name="Delgado", company_name="Anduril", visibility="private"
    )
    hp = auth_headers(teammate, personal)
    await client.post(
        f"/api/v1/contacts/{p['id']}/facts", headers=hp, json={"category": "interest", "content": "Sailing"}
    )
    await client.post(
        "/api/v1/interactions", headers=hp, json={"contact_id": p["id"], "kind": "call", "body": "Caught up."}
    )
    r = await client.post(f"/api/v1/contacts/{p['id']}/share", headers=hp, json={"target_workspace_id": org})
    assert r.status_code == 201, r.text
    shared = r.json()
    assert shared["workspace_id"] == org and shared["origin_contact_id"] == p["id"]
    assert shared["visibility"] == "team" and shared["company"]["name"] == "Anduril"
    ho = auth_headers(owner, org)
    assert (await client.get(f"/api/v1/contacts/{shared['id']}", headers=ho)).status_code == 200
    facts = await client.get(f"/api/v1/contacts/{shared['id']}/facts", headers=ho)
    assert [f["content"] for f in facts.json()] == ["Sailing"]
    tl = await client.get(f"/api/v1/contacts/{shared['id']}/timeline", headers=ho)
    assert [e["kind"] for e in tl.json()["items"]] == ["call"]
    # copying back to personal works for the author only
    assert (await client.post(f"/api/v1/contacts/{shared['id']}/copy-to-personal", headers=ho)).status_code == 403
    r = await client.post(f"/api/v1/contacts/{shared['id']}/copy-to-personal", headers=auth_headers(teammate, org))
    assert r.status_code == 201, r.text
    assert r.json()["workspace_id"] == personal and r.json()["visibility"] == "private"
    # a contact already in personal cannot be shared to a workspace the user is not in
    r = await client.post(
        f"/api/v1/contacts/{p['id']}/share", headers=hp, json={"target_workspace_id": str(uuid.uuid4())}
    )
    assert r.status_code == 403


async def test_search_and_companies_crud(
    client: httpx.AsyncClient, owner: AuthUser, viewer: AuthUser, org: str
) -> None:
    h = auth_headers(owner, org)
    r = await client.post(
        "/api/v1/companies", headers=h, json={"name": "NASA", "industry": "government", "type": "government"}
    )
    assert r.status_code == 201, r.text
    nasa = r.json()
    assert (await client.post("/api/v1/companies", headers=h, json={"name": "nasa"})).status_code == 409
    r = await client.patch(f"/api/v1/companies/{nasa['id']}", headers=h, json={"domain": "nasa.gov"})
    assert r.json()["domain"] == "nasa.gov"
    assert (
        await client.delete(f"/api/v1/companies/{nasa['id']}", headers=auth_headers(viewer, org))
    ).status_code == 403
    s = await client.get("/api/v1/search", headers=h, params={"q": "Johnson"})
    assert s.status_code == 200
    assert any(c["display_name"] == "Michael Johnson" for c in s.json()["contacts"])
    s = await client.get("/api/v1/search", headers=h, params={"q": "cost sheet"})
    assert s.json()["interactions"], "tsvector search over interaction bodies"
    assert (await client.delete(f"/api/v1/companies/{nasa['id']}", headers=h)).status_code == 204
