from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import AiStatus, InteractionDirection, InteractionKind, InteractionSource, SentimentLabel


class InteractionCreate(BaseModel, extra="forbid"):
    contact_id: UUID
    kind: InteractionKind = InteractionKind.note
    direction: InteractionDirection = InteractionDirection.mutual
    occurred_at: datetime | None = None
    subject: str | None = Field(default=None, max_length=200)
    body: str = Field(default="", max_length=20000)
    summary: str | None = Field(default=None, max_length=500)
    sentiment: SentimentLabel | None = None
    sentiment_score: float | None = Field(default=None, ge=-1, le=1)
    extract: bool = False


class InteractionUpdate(BaseModel, extra="forbid"):
    kind: InteractionKind | None = None
    direction: InteractionDirection | None = None
    occurred_at: datetime | None = None
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=20000)
    summary: str | None = Field(default=None, max_length=500)
    sentiment: SentimentLabel | None = None
    sentiment_score: float | None = Field(default=None, ge=-1, le=1)


class InteractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    contact_id: UUID | None
    user_id: UUID
    kind: InteractionKind
    direction: InteractionDirection
    occurred_at: datetime
    subject: str | None
    body: str
    summary: str | None
    sentiment: SentimentLabel | None
    sentiment_score: float | None
    source: InteractionSource
    ai_status: AiStatus
    ai_extraction: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
