from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.enums import MembershipStatus, WorkspaceKind, WorkspaceRole


class Goals(BaseModel, extra="forbid"):
    close_deals: bool = False
    expand_network: bool = False
    strengthen: bool = False
    track_roi: bool = False
    free_text: str = Field(default="", max_length=500)


class InterestIn(BaseModel, extra="forbid"):
    kind: Literal["professional", "personal"]
    value: str = Field(min_length=1, max_length=60)


class InterestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    value: str


class MembershipRead(BaseModel):
    workspace_id: UUID
    workspace_name: str
    kind: WorkspaceKind
    slug: str | None
    role: WorkspaceRole
    status: MembershipStatus
    settings: dict[str, Any]


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str
    role_title: str | None
    timezone: str
    avatar_path: str | None
    goals: dict[str, Any]
    onboarding_step: int
    onboarding_completed_at: datetime | None
    default_workspace_id: UUID | None
    created_at: datetime


class MeRead(BaseModel):
    profile: ProfileRead
    interests: list[InterestRead]
    memberships: list[MembershipRead]


def _check_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Unknown timezone") from exc
    return value


class MeUpdate(BaseModel, extra="forbid"):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    role_title: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)
    goals: Goals | None = None
    default_workspace_id: UUID | None = None
    interests: list[InterestIn] | None = Field(default=None, max_length=40)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        return _check_timezone(v) if v else v


class OnboardingProfile(BaseModel, extra="forbid"):
    full_name: str = Field(min_length=1, max_length=120)
    role_title: str = Field(default="", max_length=120)
    timezone: str = Field(default="UTC", max_length=64)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        return _check_timezone(v)


class OnboardingUpdate(BaseModel, extra="forbid"):
    """One call per step so progress survives reloads.

    Steps: 1 profile, 2 interests, 3 goals, 4 integrations, 5 done.
    """

    step: int = Field(ge=1, le=5)
    profile: OnboardingProfile | None = None
    interests: list[InterestIn] | None = Field(default=None, max_length=40)
    goals: Goals | None = None
