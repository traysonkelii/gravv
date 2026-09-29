from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import OpportunityRole, OpportunityStatus
from app.domain.companies.schemas import CompanySummary


class OpportunityCreate(BaseModel, extra="forbid"):
    name: str = Field(min_length=1, max_length=160)
    company_id: UUID | None = None
    company_name: str | None = Field(default=None, max_length=120)
    value_cents: int = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    stage: str = Field(default="qualifying", max_length=40)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close: date | None = None
    status: OpportunityStatus = OpportunityStatus.open
    notes: str | None = Field(default=None, max_length=4000)


class OpportunityUpdate(BaseModel, extra="forbid"):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    company_id: UUID | None = None
    company_name: str | None = Field(default=None, max_length=120)
    value_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    stage: str | None = Field(default=None, max_length=40)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close: date | None = None
    status: OpportunityStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)


class OpportunityContactRead(BaseModel):
    contact_id: UUID
    display_name: str
    honorific: str | None
    role: OpportunityRole
    gravity_score: int


class OpportunityRead(BaseModel):
    id: UUID
    workspace_id: UUID
    owner_user_id: UUID
    company: CompanySummary | None
    name: str
    value_cents: int
    currency: str
    stage: str
    probability: int | None
    expected_close: date | None
    status: OpportunityStatus
    notes: str | None
    contacts: list[OpportunityContactRead]
    created_at: datetime
    updated_at: datetime


class OpportunityContactPut(BaseModel, extra="forbid"):
    role: OpportunityRole = OpportunityRole.other
