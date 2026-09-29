from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import FactCategory, FactSource


class FactCreate(BaseModel, extra="forbid"):
    category: FactCategory
    content: str = Field(min_length=1, max_length=500)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: FactSource = FactSource.manual


class FactUpdate(BaseModel, extra="forbid"):
    category: FactCategory | None = None
    content: str | None = Field(default=None, min_length=1, max_length=500)
    confidence: float | None = Field(default=None, ge=0, le=1)


class FactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    contact_id: UUID
    category: FactCategory
    content: str
    confidence: float
    source: FactSource
    source_interaction_id: UUID | None
    is_active: bool
    superseded_by: UUID | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
