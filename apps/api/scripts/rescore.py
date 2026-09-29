"""Scores every contact and generates insights for every workspace, inline (worker role). Used after seeding
and as an operational tool: uv run python -m scripts.rescore"""

import asyncio

from sqlalchemy import text

from app.db.session import worker_session
from app.scoring.compute import rescore_workspace
from app.scoring.rules import generate_for_workspace


async def main() -> None:
    async with worker_session() as s:
        workspaces = (await s.execute(text("select id, name from workspaces"))).all()
    for ws_id, name in workspaces:
        async with worker_session() as s:
            scored = await rescore_workspace(s, ws_id)
            insights = await generate_for_workspace(s, ws_id)
        print(f"{name}: scored {scored} contacts, {insights} new insights")


if __name__ == "__main__":
    asyncio.run(main())
