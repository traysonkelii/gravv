from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import CompanyType


class CompanyCreate(BaseModel, extra="forbid"):
    name: str = Field(min_length=1, max_length=120)
    domain: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=60)
    type: CompanyType = CompanyType.other
    notes: str | None = Field(default=None, max_length=2000)


class CompanyUpdate(BaseModel, extra="forbid"):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    domain: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=60)
    type: CompanyType | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    name: str
    domain: str | None
    industry: str | None
    type: CompanyType
    notes: str | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class CompanySummary(BaseModel):
    id: UUID
    name: str
    industry: str | None = None
