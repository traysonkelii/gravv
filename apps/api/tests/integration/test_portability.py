"""Exports, departure export automation, retention purge, and account deletion."""

import io
import json
import uuid
import zipfile

import httpx
import pytest
from sqlalchemy import text

from app.db.session import worker_session
from app.jobs.runner import run_job_now
from tests.conftest import AuthAdmin, AuthUser, auth_headers, create_org, mint_token


async def _seed_user_data(client: httpx.AsyncClient, user: AuthUser, ws: str, label: str) -> str:
    h = auth_headers(user, ws)
    c = (
        await client.post("/api/v1/contacts", headers=h, json={"first_name": label, "last_name": "Export", "company_name": f"{label} Co"})
    ).json()
    await client.post("/api/v1/interactions", headers=h, json={"contact_id": c["id"], "kind": "note", "body": f"{label} note body."})
    await client.post(f"/api/v1/contacts/{c['id']}/facts", headers=h, json={"category": "interest", "content": f"{label} interest"})
    await client.post("/api/v1/tasks", headers=h, json={"title": f"{label} task", "contact_id": c["id"]})
    return str(c["id"])


async def _download(client: httpx.AsyncClient, user: AuthUser, export_id: str) -> tuple[dict[str, object], zipfile.ZipFile]:
    r = await client.get(f"/api/v1/exports/{export_id}", headers=auth_headers(user))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "succeeded" and body["download_url"], body
    async with httpx.AsyncClient(timeout=30) as dl:
        blob = await dl.get(body["download_url"])
        assert blob.status_code == 200, blob.text
    return body, zipfile.ZipFile(io.BytesIO(blob.content))


async def test_personal_export_contains_my_data(client: httpx.AsyncClient, auth_admin: AuthAdmin) -> None:
    user = await auth_admin.create_user("exp", "Eve Export")
    me = (await client.get("/api/v1/me", headers=auth_headers(user))).json()
    personal = next(m["workspace_id"] for m in me["memberships"] if m["kind"] == "personal")
    await _seed_user_data(client, user, personal, "Personal")
    r = await client.post("/api/v1/me/export", headers=auth_headers(user), json={"scope": "personal"})
    assert r.status_code == 202, r.text
    accepted = r.json()
    assert await run_job_now(uuid.UUID(accepted["job_id"])) == "succeeded"
    body, zf = await _download(client, user, accepted["export_id"])
    names = set(zf.namelist())
    assert {"README.txt", "profile.json", "contacts.json", "contacts.csv", "interactions.json", "facts.csv", "tasks.json"} <= names
    contacts = json.loads(zf.read("contacts.json"))
    assert [c["display_name"] for c in contacts] == ["Personal Export"]
    interactions = json.loads(zf.read("interactions.json"))
    assert interactions and interactions[0]["body"] == "Personal note body."
    assert "Personal Export" in zf.read("contacts.csv").decode()
    assert body["expires_at"]
    listing = (await client.get("/api/v1/me/exports", headers=auth_headers(user))).json()
    assert listing[0]["id"] == accepted["export_id"]


async def test_my_contributions_and_workspace_scopes(client: httpx.AsyncClient, auth_admin: AuthAdmin) -> None:
    owner = await auth_admin.create_user("expo", "Olga Owner")
    member = await auth_admin.create_user("expm", "Manny Member")
    ws = str(await create_org(owner, "Export Org"))
    async with worker_session() as s:
        await s.execute(
            text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"), {"ws": ws, "u": member.id}
        )
    await _seed_user_data(client, owner, ws, "Owner")
    await _seed_user_data(client, member, ws, "Member")
    # my contributions: only the member's own rows
    r = await client.post("/api/v1/me/export", headers=auth_headers(member, ws), json={"scope": "my_contributions"})
    assert r.status_code == 202, r.text
    assert await run_job_now(uuid.UUID(r.json()["job_id"])) == "succeeded"
    _, zf = await _download(client, member, r.json()["export_id"])
    assert [c["display_name"] for c in json.loads(zf.read("contacts.json"))] == ["Member Export"]
    assert all(i["body"].startswith("Member") for i in json.loads(zf.read("interactions.json")))
    # workspace export: admins only, contains everything
    assert (await client.post(f"/api/v1/workspaces/{ws}/export", headers=auth_headers(member, ws))).status_code == 403
    r = await client.post(f"/api/v1/workspaces/{ws}/export", headers=auth_headers(owner, ws))
    assert r.status_code == 202, r.text
    assert await run_job_now(uuid.UUID(r.json()["job_id"])) == "succeeded"
    _, zf = await _download(client, owner, r.json()["export_id"])
    assert {c["display_name"] for c in json.loads(zf.read("contacts.json"))} == {"Owner Export", "Member Export"}
    # another user cannot read the export row
    assert (await client.get(f"/api/v1/exports/{r.json()['export_id']}", headers=auth_headers(member))).status_code == 404


async def test_departure_enqueues_contribution_export_with_email(client: httpx.AsyncClient, auth_admin: AuthAdmin) -> None:
    owner = await auth_admin.create_user("depo", "Dora Owner")
    leaver = await auth_admin.create_user("depl", "Lee Leaver")
    ws = str(await create_org(owner, "Departure Org"))
    async with worker_session() as s:
        await s.execute(
            text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"), {"ws": ws, "u": leaver.id}
        )
    await _seed_user_data(client, leaver, ws, "Leaver")
    r = await client.patch(f"/api/v1/workspaces/{ws}/members/{leaver.id}", headers=auth_headers(owner), json={"status": "departed"})
    assert r.status_code == 200, r.text
    async with worker_session() as s:
        row = (
            await s.execute(
                text(
                    "select id, payload from jobs where kind = 'export.build' and payload->>'user_id' = :u order by created_at desc limit 1"
                ),
                {"u": leaver.id},
            )
        ).first()
    assert row is not None and row[1]["scope"] == "my_contributions" and row[1]["notify_email"] == leaver.email
    assert await run_job_now(uuid.UUID(str(row[0]))) == "succeeded"
    async with httpx.AsyncClient(base_url="http://127.0.0.1:54324", timeout=10) as mail:
        found = (await mail.get("/api/v1/search", params={"query": f"to:{leaver.email} subject:export", "limit": 1})).json()
    assert found["messages"], "departure export email not delivered"


async def test_retention_purge(client: httpx.AsyncClient, auth_admin: AuthAdmin) -> None:
    user = await auth_admin.create_user("purge", "Pat Purge")
    ws = str(await create_org(user, "Purge Org"))
    h = auth_headers(user, ws)
    old = (await client.post("/api/v1/contacts", headers=h, json={"first_name": "Old", "last_name": "Gone"})).json()
    recent = (await client.post("/api/v1/contacts", headers=h, json={"first_name": "Recent", "last_name": "Kept"})).json()
    for c in (old, recent):
        assert (await client.delete(f"/api/v1/contacts/{c['id']}", headers=h)).status_code == 204
    async with worker_session() as s:
        await s.execute(text("update contacts set deleted_at = now() - interval '45 days' where id = :id"), {"id": old["id"]})
        job_id = await s.scalar(
            text(
                "insert into jobs (kind, payload, run_after) values ('retention.purge', '{}'::jsonb, "
                "now() + interval '1 hour') returning id"
            )
        )
    assert await run_job_now(uuid.UUID(str(job_id))) == "succeeded"
    async with worker_session() as s:
        rows = (await s.execute(text("select id::text from contacts where id in (:a, :b)"), {"a": old["id"], "b": recent["id"]})).all()
    assert {r[0] for r in rows} == {recent["id"]}


async def test_account_deletion_tombstones_org_records(client: httpx.AsyncClient, auth_admin: AuthAdmin) -> None:
    owner = await auth_admin.create_user("delo", "Owen Owner")
    doomed = await auth_admin.create_user("deld", "Dana Doomed")
    ws = str(await create_org(owner, "Deletion Org"))
    async with worker_session() as s:
        await s.execute(
            text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"), {"ws": ws, "u": doomed.id}
        )
    org_contact = await _seed_user_data(client, doomed, ws, "OrgSide")
    me = (await client.get("/api/v1/me", headers=auth_headers(doomed))).json()
    personal = next(m["workspace_id"] for m in me["memberships"] if m["kind"] == "personal")
    personal_contact = await _seed_user_data(client, doomed, personal, "PersonalSide")

    stale = AuthUser(id=doomed.id, email=doomed.email, token=mint_token(auth_admin.settings, doomed.id, doomed.email, ttl=900))
    import jwt as pyjwt

    old_claims = pyjwt.decode(stale.token, options={"verify_signature": False})
    old_claims["iat"] = old_claims["iat"] - 900
    stale_token = pyjwt.encode(old_claims, auth_admin.settings.supabase_jwt_secret, algorithm="HS256")
    r = await client.delete("/api/v1/me", headers={"Authorization": f"Bearer {stale_token}"})
    assert r.status_code == 403 and r.json()["type"].endswith("/reauthentication_required")

    r = await client.delete("/api/v1/me", headers=auth_headers(doomed))
    assert r.status_code == 204, r.text
    assert await auth_admin.get_user_exists(doomed.id) is False
    async with worker_session() as s:
        prof = (await s.execute(text("select full_name, email, deleted_at from profiles where id = :u"), {"u": doomed.id})).first()
        org_row = (await s.execute(text("select owner_user_id, deleted_at from contacts where id = :c"), {"c": org_contact})).first()
        personal_row = (await s.execute(text("select 1 from contacts where id = :c"), {"c": personal_contact})).first()
        membership = await s.scalar(
            text("select status::text from memberships where workspace_id = :ws and user_id = :u"), {"ws": ws, "u": doomed.id}
        )
    assert prof is not None and prof[0] == "Former member" and prof[1].startswith("deleted-") and prof[2] is not None
    assert org_row is not None and str(org_row[0]) == doomed.id and org_row[1] is None, (
        "organization record kept, attributed to the tombstone"
    )
    assert personal_row is None, "personal data removed"
    assert membership == "departed"
    listing = (await client.get(f"/api/v1/contacts/{org_contact}", headers=auth_headers(owner, ws))).json()
    assert listing["display_name"] == "OrgSide Export"


async def test_owner_with_members_must_transfer_first(client: httpx.AsyncClient, auth_admin: AuthAdmin) -> None:
    owner = await auth_admin.create_user("delown", "Otis Owner")
    other = await auth_admin.create_user("delmem", "Mia Member")
    ws = str(await create_org(owner, "Blocked Org"))
    async with worker_session() as s:
        await s.execute(text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"), {"ws": ws, "u": other.id})
    r = await client.delete("/api/v1/me", headers=auth_headers(owner))
    assert r.status_code == 409 and "Transfer ownership" in r.json()["title"]
    _ = pytest
