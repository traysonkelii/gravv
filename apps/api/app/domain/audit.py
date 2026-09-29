"""Audit entries through the security definer function (Section 6.7)."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def write_audit(
    session: AsyncSession,
    workspace_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    diff: dict[str, Any] | None = None,
) -> None:
    await session.execute(
        text("select write_audit(:ws, :action, :etype, :eid, cast(:diff as jsonb))"),
        {
            "ws": workspace_id,
            "action": action,
            "etype": entity_type,
            "eid": entity_id,
            "diff": json.dumps(diff, default=str) if diff is not None else None,
        },
    )
