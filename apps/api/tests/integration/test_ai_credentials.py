import json
import uuid

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.ai.resolve import load_workspace_keys
from app.db.session import worker_session
from tests.conftest import AuthAdmin, AuthUser, auth_headers, create_org, rls_session

KEY = "sk-ant-api03-" + "a" * 40


@pytest.fixture(scope="module")
async def owner(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("aio", "Ada Owner")


@pytest.fixture(scope="module")
async def member(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("aim", "Mo Member")


@pytest.fixture(scope="module")
async def org(owner: AuthUser, member: AuthUser) -> str:
    ws = str(await create_org(owner, "AI Org"))
    async with worker_session() as s:
        await s.execute(
            text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"), {"ws": ws, "u": member.id}
        )
    return ws


async def test_status_without_keys_uses_server_fallback(client: httpx.AsyncClient, owner: AuthUser, org: str) -> None:
    r = await client.get(f"/api/v1/workspaces/{org}/ai", headers=auth_headers(owner, org))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm"] == {"configured": True, "provider": "fake", "source": "fake"}  # APP_ENV=test forces the fake
    assert body["credentials"] == [] and body["can_manage"] is True


async def test_put_stores_hint_only_and_worker_decrypts(client: httpx.AsyncClient, owner: AuthUser, member: AuthUser, org: str) -> None:
    h = auth_headers(owner, org)
    bad = await client.put(f"/api/v1/workspaces/{org}/ai/anthropic", headers=h, json={"api_key": "not-a-key-at-all-really"})
    assert bad.status_code == 422 and bad.json()["type"].endswith("/invalid_api_key")
    r = await client.put(f"/api/v1/workspaces/{org}/ai/anthropic", headers=h, json={"api_key": KEY, "model": "claude-sonnet-5"})
    assert r.status_code == 200, r.text
    assert r.json()["key_hint"] == "aaaa" and r.json()["model"] == "claude-sonnet-5" and r.json()["verified_at"]
    assert KEY not in r.text
    status = (await client.get(f"/api/v1/workspaces/{org}/ai", headers=h)).json()
    assert status["llm"] == {"configured": True, "provider": "anthropic", "source": "workspace"}
    assert KEY not in json.dumps(status)
    # a member sees the status but no credential rows and cannot manage
    mine = (await client.get(f"/api/v1/workspaces/{org}/ai", headers=auth_headers(member, org))).json()
    assert mine["llm"]["provider"] == "anthropic" and mine["credentials"] == [] and mine["can_manage"] is False
    assert (
        await client.put(f"/api/v1/workspaces/{org}/ai/openai", headers=auth_headers(member, org), json={"api_key": "sk-" + "b" * 40})
    ).status_code == 403
    # the worker decrypts the real key; the API role cannot even read the column
    async with worker_session() as s:
        keys = await load_workspace_keys(s, org)
    assert keys["anthropic"].api_key == KEY and keys["anthropic"].model == "claude-sonnet-5"
    with pytest.raises(DBAPIError):
        async with rls_session(owner) as s:
            await s.execute(text("select key_enc from ai_credentials where workspace_id = :ws"), {"ws": org})
    async with rls_session(member) as s:
        assert await s.scalar(text("select count(*) from ai_credentials where workspace_id = :ws"), {"ws": org}) == 0


async def test_replace_and_delete(client: httpx.AsyncClient, owner: AuthUser, org: str) -> None:
    h = auth_headers(owner, org)
    r = await client.put(f"/api/v1/workspaces/{org}/ai/anthropic", headers=h, json={"api_key": "sk-ant-api03-" + "z" * 40, "verify": False})
    assert r.status_code == 200 and r.json()["key_hint"] == "zzzz" and r.json()["verified_at"] is None
    async with worker_session() as s:
        keys = await load_workspace_keys(s, org)
    assert keys["anthropic"].api_key.endswith("zzzz")
    assert (await client.delete(f"/api/v1/workspaces/{org}/ai/anthropic", headers=h)).status_code == 204
    assert (await client.delete(f"/api/v1/workspaces/{org}/ai/anthropic", headers=h)).status_code == 404
    status = (await client.get(f"/api/v1/workspaces/{org}/ai", headers=h)).json()
    assert status["credentials"] == [] and status["llm"]["source"] == "fake"


async def test_personal_workspace_owner_manages_own_keys(client: httpx.AsyncClient, auth_admin: AuthAdmin) -> None:
    user = await auth_admin.create_user("aip", "Pia Personal")
    me = (await client.get("/api/v1/me", headers=auth_headers(user))).json()
    personal = next(m["workspace_id"] for m in me["memberships"] if m["kind"] == "personal")
    r = await client.put(f"/api/v1/workspaces/{personal}/ai/deepgram", headers=auth_headers(user, personal), json={"api_key": "d" * 40})
    assert r.status_code == 200, r.text
    status = (await client.get(f"/api/v1/workspaces/{personal}/ai", headers=auth_headers(user, personal))).json()
    assert status["transcription"] == {"configured": True, "provider": "deepgram", "source": "workspace"}
    assert (await client.get(f"/api/v1/workspaces/{uuid.uuid4()}/ai", headers=auth_headers(user, personal))).status_code == 400
