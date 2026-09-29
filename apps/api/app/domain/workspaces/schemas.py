import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.enums import MembershipStatus, WorkspaceKind, WorkspaceRole
from app.domain.common import EmailAddress

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])?$")


class WorkspaceSettings(BaseModel, extra="forbid"):
    default_contact_visibility: str = Field(default="team", pattern="^(team|private)$")
    default_cadence_days: int = Field(default=30, ge=1, le=365)
    auto_apply_low_risk_facts: bool = False
    require_mfa: bool = False
    retain_audio: bool = False
    ai_daily_token_budget: int = Field(default=500_000, ge=0, le=50_000_000)
    narrate_insights_with_llm: bool = False


class WorkspaceCreate(BaseModel, extra="forbid"):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=40)
    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not SLUG_RE.match(v):
            raise ValueError("Use lowercase letters, numbers, and hyphens (3 to 40 characters)")
        return v


class WorkspaceUpdate(BaseModel, extra="forbid"):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=40)
    settings: WorkspaceSettings | None = None

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not SLUG_RE.match(v):
            raise ValueError("Use lowercase letters, numbers, and hyphens (3 to 40 characters)")
        return v


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: WorkspaceKind
    name: str
    slug: str | None
    owner_user_id: UUID
    settings: dict[str, Any]
    plan: str
    created_at: datetime
    my_role: WorkspaceRole | None = None


class MemberRead(BaseModel):
    user_id: UUID
    full_name: str
    role_title: str | None
    avatar_path: str | None
    email: str
    role: WorkspaceRole
    status: MembershipStatus
    joined_at: datetime
    departed_at: datetime | None


class MemberUpdate(BaseModel, extra="forbid"):
    role: WorkspaceRole | None = None
    status: MembershipStatus | None = None


class InvitationCreate(BaseModel, extra="forbid"):
    email: EmailAddress
    role: WorkspaceRole = WorkspaceRole.member


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    email: str
    role: WorkspaceRole
    invited_by: UUID
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationPeek(BaseModel):
    workspace_name: str
    role: WorkspaceRole
    inviter_name: str
    email: str
    expires_at: datetime
    accepted: bool
    expired: bool


class AcceptResult(BaseModel):
    workspace_id: UUID
