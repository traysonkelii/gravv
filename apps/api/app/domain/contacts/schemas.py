from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import Band, ContactStatus, ContactVisibility, InteractionKind, RelationshipType
from app.domain.common import EmailAddress
from app.domain.companies.schemas import CompanySummary

ContactSort = Literal["updated", "gravity", "last_interaction", "name", "next_due"]


class ContactCreate(BaseModel, extra="forbid"):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    honorific: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, max_length=120)
    company_id: UUID | None = None
    company_name: str | None = Field(default=None, max_length=120)
    emails: list[EmailAddress] = Field(default_factory=list, max_length=20)
    phones: list[str] = Field(default_factory=list, max_length=20)
    location: str | None = Field(default=None, max_length=120)
    relationship_type: RelationshipType = RelationshipType.other
    visibility: ContactVisibility | None = None
    tags: list[str] = Field(default_factory=list, max_length=50)
    cadence_days: int = Field(default=30, ge=1, le=365)


class ContactUpdate(BaseModel, extra="forbid"):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    honorific: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, max_length=120)
    company_id: UUID | None = None
    company_name: str | None = Field(default=None, max_length=120)
    emails: list[EmailAddress] | None = Field(default=None, max_length=20)
    phones: list[str] | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=120)
    relationship_type: RelationshipType | None = None
    visibility: ContactVisibility | None = None
    status: ContactStatus | None = None
    tags: list[str] | None = Field(default=None, max_length=50)
    cadence_days: int | None = Field(default=None, ge=1, le=365)


class InteractionSummary(BaseModel):
    id: UUID
    kind: InteractionKind
    occurred_at: datetime
    summary: str | None
    subject: str | None


class ContactProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    summary: str
    communication_style: str | None
    remember: list[str]
    risks: list[str]
    talking_points: list[str]
    common_ground: list[str]
    model: str | None
    prompt_version: str | None
    generated_at: datetime | None
    stale: bool


class ContactRead(BaseModel):
    id: UUID
    workspace_id: UUID
    owner_user_id: UUID
    display_name: str
    honorific: str | None
    first_name: str
    last_name: str
    title: str | None
    company: CompanySummary | None
    emails: list[str]
    phones: list[str]
    location: str | None
    relationship_type: RelationshipType
    visibility: ContactVisibility
    status: ContactStatus
    tags: list[str]
    cadence_days: int
    gravity_score: int
    band: Band
    score_delta_30d: int | None
    last_interaction: InteractionSummary | None
    next_due_at: datetime | None
    open_task_count: int
    open_opportunity_value_cents: int
    origin_contact_id: UUID | None
    profile: ContactProfileRead | None = None
    created_at: datetime
    updated_at: datetime


class ShareRequest(BaseModel, extra="forbid"):
    target_workspace_id: UUID


class TimelineEntry(BaseModel):
    entry_type: Literal["interaction", "task", "score"]
    id: UUID
    ts: datetime
    kind: str
    title: str
    body: str
    meta: dict[str, Any]
