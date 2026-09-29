from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Range = Literal["today", "week", "month", "quarter", "year"]
Scope = Literal["me", "team"]


class AnalyticsSummary(BaseModel):
    range: str
    scope: Scope
    contact_count: int
    contact_count_delta: int
    active_count: int
    engagement_rate: float
    avg_gravity: int
    avg_gravity_delta: int
    pipeline_value_cents: int
    pipeline_delta_pct: float
    open_opportunity_count: int
    due_count: int


class BandCount(BaseModel):
    band: str
    count: int


class SeriesPoint(BaseModel):
    period: str
    kind: str
    count: int


class TopContact(BaseModel):
    id: UUID
    display_name: str
    honorific: str | None
    company_name: str | None
    gravity_score: int
    band: str
    status: str
    last_interaction_at: str | None
    deal_value_cents: int


class MemberMetrics(BaseModel):
    user_id: UUID
    full_name: str
    role: str
    contact_count: int
    avg_gravity: int
    interactions_in_range: int
    pipeline_value_cents: int
    overdue_tasks: int
