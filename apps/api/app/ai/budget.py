"""Per-workspace daily token budget (Section 7.7), enforced by the worker before every provider call."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import Usage

DEFAULT_BUDGET = 500_000

_BUDGET_SQL = text(
    "select coalesce((select (settings->>'ai_daily_token_budget')::bigint from workspaces where id = :ws), :default) "
    "as budget, "
    "coalesce((select sum(input_tokens + output_tokens) from ai_usage "
    "where workspace_id = :ws and created_at >= date_trunc('day', now())), 0) as used"
)


class BudgetExceeded(RuntimeError):
    pass


async def check_budget(session: AsyncSession, workspace_id: UUID) -> None:
    row = (await session.execute(_BUDGET_SQL, {"ws": workspace_id, "default": DEFAULT_BUDGET})).first()
    assert row is not None
    if row[1] >= row[0]:
        raise BudgetExceeded(f"workspace {workspace_id} used {row[1]} of {row[0]} tokens today")


async def record_usage(
    session: AsyncSession, workspace_id: UUID, user_id: UUID | None, kind: str, model: str, usage: Usage
) -> None:
    await session.execute(
        text(
            "insert into ai_usage (workspace_id, user_id, kind, model, input_tokens, output_tokens) "
            "values (:ws, :uid, :kind, :model, :i, :o)"
        ),
        {
            "ws": workspace_id,
            "uid": user_id,
            "kind": kind,
            "model": model,
            "i": usage.input_tokens,
            "o": usage.output_tokens,
        },
    )
