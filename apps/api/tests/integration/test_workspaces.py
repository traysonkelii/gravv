import re

import httpx
import pytest

from tests.conftest import AuthAdmin, AuthUser, auth_headers, mint_token

MAILPIT = "http://127.0.0.1:54324"


@pytest.fixture(scope="module")
async def owner(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("owner", "Olivia Owner")


@pytest.fixture(scope="module")
async def member(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("member", "Max Member")


@pytest.fixture(scope="module")
async def outsider(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("outsider", "Otto Outsider")


@pytest.fixture(scope="module")
async def org(client: httpx.AsyncClient, owner: AuthUser) -> dict[str, object]:
    r = await client.post(
        "/api/v1/workspaces",
        headers=auth_headers(owner),
        json={"name": "Meridian Test", "slug": "meridian-test", "settings": {"default_cadence_days": 21}},
    )
    assert r.status_code == 201, r.text
    body: dict[str, object] = r.json()
    assert body["my_role"] == "owner"
    return body


async def test_workspaces_list_includes_org(client: httpx.AsyncClient, owner: AuthUser, org: dict[str, object]) -> None:
    r = await client.get("/api/v1/workspaces", headers=auth_headers(owner))
    assert r.status_code == 200
    kinds = sorted(w["kind"] for w in r.json())
    assert kinds == ["organization", "personal"]


async def test_slug_is_validated(client: httpx.AsyncClient, owner: AuthUser) -> None:
    r = await client.post("/api/v1/workspaces", headers=auth_headers(owner), json={"name": "X", "slug": "Bad Slug"})
    assert r.status_code == 422


async def test_duplicate_slug_is_conflict(client: httpx.AsyncClient, owner: AuthUser, org: dict[str, object]) -> None:
    r = await client.post("/api/v1/workspaces", headers=auth_headers(owner), json={"name": "Y", "slug": "meridian-test"})
    assert r.status_code == 409
    assert r.json()["type"].endswith("/conflict")


async def test_outsider_cannot_read_or_update(client: httpx.AsyncClient, outsider: AuthUser, org: dict[str, object]) -> None:
    ws = org["id"]
    assert (await client.get(f"/api/v1/workspaces/{ws}", headers=auth_headers(outsider))).status_code == 403
    r = await client.patch(f"/api/v1/workspaces/{ws}", headers=auth_headers(outsider), json={"name": "Hijack"})
    assert r.status_code == 403
    assert (await client.get(f"/api/v1/workspaces/{ws}/members", headers=auth_headers(outsider))).status_code == 403


async def test_update_merges_settings(client: httpx.AsyncClient, owner: AuthUser, org: dict[str, object]) -> None:
    ws = org["id"]
    r = await client.patch(
        f"/api/v1/workspaces/{ws}",
        headers=auth_headers(owner),
        json={"name": "Meridian Test 2", "settings": {"require_mfa": True, "default_cadence_days": 21}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Meridian Test 2"
    assert r.json()["settings"]["require_mfa"] is True
    assert r.json()["settings"]["default_cadence_days"] == 21


async def _latest_invite_link(to_email: str) -> str:
    async with httpx.AsyncClient(base_url=MAILPIT, timeout=10) as c:
        r = await c.get("/api/v1/search", params={"query": f"to:{to_email}", "limit": 1})
        r.raise_for_status()
        msgs = r.json()["messages"]
        assert msgs, "no invitation email in the local inbox"
        m = await c.get(f"/api/v1/message/{msgs[0]['ID']}")
        text = m.json()["Text"]
    match = re.search(r"http://[^\s]+/invite/([A-Za-z0-9_-]+)", text)
    assert match, text
    return match.group(0)


async def test_invite_accept_flow(client: httpx.AsyncClient, owner: AuthUser, member: AuthUser, org: dict[str, object]) -> None:
    ws = org["id"]
    r = await client.post(
        f"/api/v1/workspaces/{ws}/invitations",
        headers=auth_headers(owner),
        json={"email": member.email, "role": "member"},
    )
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["email"] == member.email and inv["accepted_at"] is None

    link = await _latest_invite_link(member.email)
    token = link.rsplit("/", 1)[1]

    peek = await client.get(f"/api/v1/invitations/{token}")
    assert peek.status_code == 200, peek.text
    assert peek.json()["workspace_name"].startswith("Meridian Test")
    assert peek.json()["inviter_name"] == "Olivia Owner"
    assert peek.json()["accepted"] is False

    assert (await client.get("/api/v1/invitations/not-a-real-token")).status_code == 404

    r = await client.post(f"/api/v1/invitations/{token}/accept", headers=auth_headers(member))
    assert r.status_code == 200, r.text
    assert r.json()["workspace_id"] == ws

    r = await client.get(f"/api/v1/workspaces/{ws}/members", headers=auth_headers(member))
    assert r.status_code == 200
    names = {m["full_name"]: m["role"] for m in r.json()}
    assert names == {"Olivia Owner": "owner", "Max Member": "member"}

    again = await client.post(f"/api/v1/invitations/{token}/accept", headers=auth_headers(member))
    assert again.status_code == 409


async def test_invite_wrong_email_cannot_accept(
    client: httpx.AsyncClient, owner: AuthUser, outsider: AuthUser, org: dict[str, object]
) -> None:
    ws = org["id"]
    target = "someone-else@test.gravv.local"
    r = await client.post(f"/api/v1/workspaces/{ws}/invitations", headers=auth_headers(owner), json={"email": target, "role": "viewer"})
    assert r.status_code == 201
    token = (await _latest_invite_link(target)).rsplit("/", 1)[1]
    r = await client.post(f"/api/v1/invitations/{token}/accept", headers=auth_headers(outsider))
    assert r.status_code == 403
    listing = await client.get(f"/api/v1/workspaces/{ws}/invitations", headers=auth_headers(owner))
    inv_id = next(i["id"] for i in listing.json() if i["email"] == target)
    assert (await client.delete(f"/api/v1/workspaces/{ws}/invitations/{inv_id}", headers=auth_headers(owner))).status_code == 204
    assert (await client.get(f"/api/v1/invitations/{token}")).status_code == 404


async def test_member_cannot_invite_or_change_roles(
    client: httpx.AsyncClient, member: AuthUser, owner: AuthUser, org: dict[str, object]
) -> None:
    ws = org["id"]
    r = await client.post(f"/api/v1/workspaces/{ws}/invitations", headers=auth_headers(member), json={"email": "x@test.gravv.local"})
    assert r.status_code == 403
    r = await client.patch(f"/api/v1/workspaces/{ws}/members/{owner.id}", headers=auth_headers(member), json={"role": "viewer"})
    assert r.status_code == 403


async def test_role_change_rules(client: httpx.AsyncClient, owner: AuthUser, member: AuthUser, org: dict[str, object]) -> None:
    ws = org["id"]
    r = await client.patch(f"/api/v1/workspaces/{ws}/members/{member.id}", headers=auth_headers(owner), json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    # admin cannot promote to admin (must be strictly below own role) nor touch the owner
    r = await client.patch(f"/api/v1/workspaces/{ws}/members/{owner.id}", headers=auth_headers(member), json={"role": "member"})
    assert r.status_code == 403
    # ownership transfer needs aal2
    r = await client.patch(f"/api/v1/workspaces/{ws}/members/{member.id}", headers=auth_headers(owner), json={"role": "owner"})
    assert r.status_code == 403 and r.json()["type"].endswith("/mfa_required")
    r = await client.patch(f"/api/v1/workspaces/{ws}/members/{member.id}", headers=auth_headers(owner), json={"role": "manager"})
    assert r.status_code == 200 and r.json()["role"] == "manager"


async def test_departure_blocks_access_immediately(
    client: httpx.AsyncClient, owner: AuthUser, member: AuthUser, org: dict[str, object]
) -> None:
    ws = org["id"]
    r = await client.patch(f"/api/v1/workspaces/{ws}/members/{member.id}", headers=auth_headers(owner), json={"status": "departed"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "departed" and r.json()["departed_at"]
    assert (await client.get(f"/api/v1/workspaces/{ws}", headers=auth_headers(member))).status_code == 403
    assert (await client.get(f"/api/v1/workspaces/{ws}/members", headers=auth_headers(member))).status_code == 403
    # personal workspace untouched
    me = await client.get("/api/v1/me", headers=auth_headers(member))
    assert [m["status"] for m in me.json()["memberships"] if m["kind"] == "personal"] == ["active"]


async def test_owner_cannot_leave_and_cannot_be_departed(client: httpx.AsyncClient, owner: AuthUser, org: dict[str, object]) -> None:
    ws = org["id"]
    assert (await client.delete(f"/api/v1/workspaces/{ws}/members/me", headers=auth_headers(owner))).status_code == 422
    r = await client.patch(f"/api/v1/workspaces/{ws}/members/{owner.id}", headers=auth_headers(owner), json={"status": "departed"})
    assert r.status_code == 422


async def test_ownership_transfer_with_mfa(
    client: httpx.AsyncClient, settings: object, owner: AuthUser, auth_admin: AuthAdmin, org: dict[str, object]
) -> None:
    ws = org["id"]
    successor = await auth_admin.create_user("successor", "Sam Successor")
    r = await client.post(
        f"/api/v1/workspaces/{ws}/invitations",
        headers=auth_headers(owner),
        json={"email": successor.email, "role": "admin"},
    )
    token = (await _latest_invite_link(successor.email)).rsplit("/", 1)[1]
    assert (await client.post(f"/api/v1/invitations/{token}/accept", headers=auth_headers(successor))).status_code == 200
    from app.config import get_settings

    strong = AuthUser(id=owner.id, email=owner.email, token=mint_token(get_settings(), owner.id, owner.email, aal="aal2"))
    r = await client.patch(f"/api/v1/workspaces/{ws}/members/{successor.id}", headers=auth_headers(strong), json={"role": "owner"})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "owner"
    me = await client.get(f"/api/v1/workspaces/{ws}", headers=auth_headers(owner))
    assert me.json()["my_role"] == "admin" and me.json()["owner_user_id"] == successor.id
    # former owner may now leave
    assert (await client.delete(f"/api/v1/workspaces/{ws}/members/me", headers=auth_headers(owner))).status_code == 204
    assert (await client.get(f"/api/v1/workspaces/{ws}", headers=auth_headers(owner))).status_code == 403
