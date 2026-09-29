from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from app.db.enums import InsightKind, InsightSeverity, InsightStatus


class InsightRead(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID | None
    contact_id: UUID | None
    contact_name: str | None
    company_id: UUID | None
    company_name: str | None
    kind: InsightKind
    severity: InsightSeverity
    title: str
    body: str
    evidence: dict[str, Any]
    suggested_action: dict[str, Any] | None
    status: InsightStatus
    expires_at: datetime | None
    generated_by: str
    created_at: datetime


class InsightStatusUpdate(BaseModel, extra="forbid"):
    status: Literal["seen", "acted", "dismissed"]


class InsightActResult(BaseModel):
    insight: InsightRead
    task_id: UUID | None = None
    navigate_to: str | None = None


class ScorePoint(BaseModel):
    scored_on: str
    score: int
    band: str
