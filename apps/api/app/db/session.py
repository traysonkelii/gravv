import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def _engine(url: str) -> AsyncEngine:
    # Supavisor transaction mode in production: no prepared statement cache, no session state.
    sep = "&" if "?" in url else "?"
    return create_async_engine(
        f"{url}{sep}prepared_statement_cache_size=0",
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"statement_cache_size": 0},
    )


@lru_cache
def api_engine() -> AsyncEngine:
    return _engine(get_settings().database_url)


@lru_cache
def worker_engine() -> AsyncEngine:
    return _engine(get_settings().database_url_worker)


@lru_cache
def api_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(api_engine(), expire_on_commit=False, autoflush=False)


@lru_cache
def worker_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(worker_engine(), expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def worker_session(user_id: str | None = None, email: str = "") -> AsyncIterator[AsyncSession]:
    """Worker transaction. Cross-tenant by default (service_role); binds a user identity when a job acts for one."""
    async with worker_session_factory()() as session, session.begin():
        if user_id is None:
            await session.execute(text("set local role service_role"))
        else:
            await session.execute(text("set local role authenticated"))
            claims = {"sub": user_id, "role": "authenticated", "email": email, "aal": "aal1"}
            await session.execute(text("select set_config('request.jwt.claims', :claims, true)"), {"claims": json.dumps(claims)})
        yield session
