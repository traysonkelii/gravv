"""Server-side calls to the Supabase Auth admin API (secret key). Never used for tenant data."""

from typing import Any

import httpx

from app.config import get_settings


def _client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(
        base_url=f"{s.supabase_url}/auth/v1/admin",
        headers={"apikey": s.supabase_secret_key, "Authorization": f"Bearer {s.supabase_secret_key}"},
        timeout=30,
    )


async def get_user(user_id: str) -> dict[str, Any] | None:
    async with _client() as c:
        r = await c.get(f"/users/{user_id}")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()  # type: ignore[no-any-return]


async def has_verified_mfa(user_id: str) -> bool:
    user = await get_user(user_id)
    factors = (user or {}).get("factors") or []
    return any(f.get("status") == "verified" for f in factors)


async def delete_user(user_id: str) -> None:
    async with _client() as c:
        r = await c.delete(f"/users/{user_id}")
    if r.status_code not in (200, 204, 404):
        r.raise_for_status()
