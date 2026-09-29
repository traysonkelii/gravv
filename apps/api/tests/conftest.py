"""Shared fixtures: test settings, auth admin helpers, token minting, RLS-bound SQL sessions, ASGI client."""

import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

os.environ["APP_ENV"] = "test"

import asyncpg
import httpx
import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import api_session_factory

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")


@pytest.fixture(scope="session")
def settings() -> Settings:
    s = get_settings()
    if not s.supabase_jwt_secret:
        pytest.skip("SUPABASE_JWT_SECRET missing; run `make env` against the local stack")
    return s


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    token: str


def mint_token(settings: Settings, user_id: str, email: str, aal: str = "aal1", ttl: int = 900) -> str:
    now = int(time.time())
    claims = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "iss": settings.auth_issuer,
        "iat": now,
        "exp": now + ttl,
        "aal": aal,
        "session_id": str(uuid.uuid4()),
    }
    return jwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")


class AuthAdmin:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.supabase_url,
            headers={
                "apikey": settings.supabase_secret_key,
                "Authorization": f"Bearer {settings.supabase_secret_key}",
            },
            timeout=30,
        )

    async def create_user(self, prefix: str, full_name: str = "Test User") -> AuthUser:
        email = f"test-{prefix}-{uuid.uuid4().hex[:8]}@test.gravv.local"
        r = await self.client.post(
            "/auth/v1/admin/users",
            json={
                "email": email,
                "password": "test-password-123",
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            },
        )
        r.raise_for_status()
        uid = r.json()["id"]
        return AuthUser(id=uid, email=email, token=mint_token(self.settings, uid, email))

    async def delete_user(self, user_id: str) -> None:
        await self.client.delete(f"/auth/v1/admin/users/{user_id}")


@pytest.fixture(scope="session")
async def auth_admin(settings: Settings) -> AsyncIterator[AuthAdmin]:
    admin = AuthAdmin(settings)
    yield admin
    await admin.client.aclose()


@pytest.fixture(scope="session")
async def superuser() -> AsyncIterator[asyncpg.Connection]:
    """Postgres owner connection for setup and teardown only. Never used by application code."""
    conn = await asyncpg.connect(POSTGRES_URL)
    yield conn
    await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def cleanup_test_users(superuser: asyncpg.Connection) -> AsyncIterator[None]:
    yield
    # Organization workspaces block the auth.users cascade through owner_user_id, so drop them first.
    await superuser.execute(
        "delete from workspaces where owner_user_id in "
        "(select id from profiles where email like 'test-%@test.gravv.local')"
    )
    await superuser.execute("delete from auth.users where email like 'test-%@test.gravv.local'")


@asynccontextmanager
async def rls_session(user: AuthUser | None) -> AsyncIterator[AsyncSession]:
    """An RLS-bound transaction exactly as the API opens it. Commits on exit."""
    async with api_session_factory()() as session, session.begin():
        if user is None:
            await session.execute(text("set local role anon"))
        else:
            await session.execute(text("set local role authenticated"))
            claims = {"sub": user.id, "role": "authenticated", "email": user.email, "aal": "aal1"}
            await session.execute(text("select set_config('request.jwt.claims', :c, true)"), {"c": json.dumps(claims)})
        yield session


@pytest.fixture(scope="session")
async def client() -> AsyncIterator[httpx.AsyncClient]:
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def auth_headers(user: AuthUser, workspace_id: str | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {user.token}"}
    if workspace_id:
        h["X-Workspace-Id"] = workspace_id
    return h


async def create_org(user: AuthUser, name: str) -> uuid.UUID:
    async with rls_session(user) as s:
        ws = await s.scalar(text("select create_organization(:n)"), {"n": name})
    assert ws is not None
    return uuid.UUID(str(ws))


def as_json(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))
