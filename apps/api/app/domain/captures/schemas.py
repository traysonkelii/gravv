from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.ai.extraction import (
    CaptureExtraction,
    ExtractedEdge,
    ExtractedFact,
    ExtractedInteraction,
    ExtractedTask,
    MentionedPerson,
)
from app.db.enums import CaptureStatus
from app.domain.contacts.schemas import ContactRead
from app.domain.interactions.schemas import InteractionRead
from app.storage import MAX_AUDIO_BYTES

IdempotencyKey = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class CaptureTextCreate(BaseModel, extra="forbid"):
    text: str = Field(min_length=1, max_length=20000)
    contact_id: UUID | None = None
    idempotency_key: str = IdempotencyKey


class VoiceUploadRequest(BaseModel, extra="forbid"):
    content_type: Literal["audio/webm", "audio/mp4", "audio/mpeg", "audio/wav"]
    size_bytes: int = Field(ge=1, le=MAX_AUDIO_BYTES)
    contact_id: UUID | None = None
    idempotency_key: str = IdempotencyKey


class VoiceUploadResponse(BaseModel):
    capture_id: UUID
    upload_url: str
    token: str
    storage_path: str
    headers: dict[str, str]


class UploadedRequest(BaseModel, extra="forbid"):
    duration_seconds: float | None = Field(default=None, ge=0, le=600)


class CaptureRead(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID
    contact_id: UUID | None
    kind: str
    status: CaptureStatus
    transcript: str | None
    raw_text: str | None
    duration_seconds: float | None
    proposal: CaptureExtraction | None
    provenance: dict[str, Any]
    interaction_id: UUID | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class CaptureConfirm(BaseModel, extra="forbid"):
    contact_id: UUID
    interaction: ExtractedInteraction
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=20)
    tasks: list[ExtractedTask] = Field(default_factory=list, max_length=20)
    edges: list[ExtractedEdge] = Field(default_factory=list, max_length=20)
    create_contacts_for: list[MentionedPerson] = Field(default_factory=list, max_length=20)


class ConfirmResult(BaseModel):
    interaction: InteractionRead
    contact: ContactRead
    created_contact_ids: list[UUID]
    fact_ids: list[UUID]
    task_ids: list[UUID]


class JobRead(BaseModel):
    id: UUID
    kind: str
    status: str
    result: dict[str, Any] | None
    last_error: str | None
    created_at: datetime
    finished_at: datetime | None


class JobAccepted(BaseModel):
    job_id: UUID | None
    deduplicated: bool
