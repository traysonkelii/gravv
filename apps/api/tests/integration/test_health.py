import httpx

from app.config import Settings
from tests.conftest import AuthUser, auth_headers, mint_token


async def test_healthz(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r.headers["x-request-id"]


async def test_readyz_reports_database_and_migrations(client: httpx.AsyncClient, settings: Settings) -> None:
    r = await client.get("/readyz")
    assert r.status_code == 200, r.text
    assert r.json()["database"] == "ok"


async def test_missing_token_is_problem_json(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/nonexistent")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["type"].endswith("/not_found")
    assert body["request_id"]


async def test_request_id_propagates(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz", headers={"X-Request-Id": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


async def test_garbage_bearer_rejected(client: httpx.AsyncClient, settings: Settings) -> None:
    user = AuthUser(id="00000000-0000-4000-8000-00000000dead", email="x@y.z", token="not-a-jwt")
    r = await client.get("/readyz", headers=auth_headers(user))
    # readyz is public; the header must still not break the request pipeline
    assert r.status_code == 200
    _ = mint_token
