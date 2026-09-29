"""Creates the demo users through the Supabase auth admin API, then loads supabase/seed.sql.

Never inserts into auth.users directly. Idempotent: existing users are left alone and the seed SQL
uses `on conflict do nothing` with fixed ids.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import httpx

from app.config import REPO_ROOT, get_settings

DEMO_PASSWORD = "demo-password-1"
USERS = [
    ("sarah@demo.gravv.local", "Sarah Chen", "Account Executive"),
    ("dan@demo.gravv.local", "Dan Okafor", "Sales Manager"),
    ("priya@demo.gravv.local", "Priya Nair", "Program Manager"),
]


def _local_keys() -> tuple[str, str]:
    settings = get_settings()
    if settings.supabase_secret_key:
        return settings.supabase_url, settings.supabase_secret_key
    out = subprocess.run(
        ["supabase", "status", "-o", "env"], check=True, capture_output=True, text=True, cwd=REPO_ROOT
    ).stdout
    env = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return settings.supabase_url, env["SECRET_KEY"].strip('"')


def ensure_user(client: httpx.Client, email: str, full_name: str, role_title: str) -> str:
    existing = client.get("/auth/v1/admin/users", params={"page": 1, "per_page": 200}).json().get("users", [])
    for u in existing:
        if u["email"].lower() == email:
            return str(u["id"])
    r = client.post(
        "/auth/v1/admin/users",
        json={
            "email": email,
            "password": DEMO_PASSWORD,
            "email_confirm": True,
            "user_metadata": {"full_name": full_name, "role_title": role_title},
        },
    )
    r.raise_for_status()
    return str(r.json()["id"])


async def load_seed_sql() -> None:
    dsn = os.environ.get("SEED_DB_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    sql = (REPO_ROOT / "supabase" / "seed.sql").read_text()
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


def main() -> None:
    url, secret = _local_keys()
    with httpx.Client(base_url=url, headers={"apikey": secret, "Authorization": f"Bearer {secret}"}, timeout=30) as c:
        for email, name, title in USERS:
            uid = ensure_user(c, email, name, title)
            print(f"user {email} {uid}")
    if not (Path(REPO_ROOT) / "supabase" / "seed.sql").exists():
        print("no seed.sql, skipping", file=sys.stderr)
        return
    asyncio.run(load_seed_sql())
    print("seed.sql loaded")


if __name__ == "__main__":
    main()
