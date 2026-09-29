import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Provider = Literal["anthropic", "openai", "deepgram"]

KEY_SHAPES: dict[str, tuple[re.Pattern[str], str]] = {
    "anthropic": (re.compile(r"^sk-ant-[A-Za-z0-9_-]{20,}$"), "Anthropic keys start with sk-ant-"),
    "openai": (re.compile(r"^sk-[A-Za-z0-9_-]{20,}$"), "OpenAI keys start with sk-"),
    "deepgram": (re.compile(r"^[A-Za-z0-9]{32,}$"), "Deepgram keys are at least 32 letters and digits"),
}


class CredentialPut(BaseModel, extra="forbid"):
    api_key: str = Field(min_length=20, max_length=512)
    model: str | None = Field(default=None, max_length=80)
    verify: bool = True

    @field_validator("api_key")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class CredentialRead(BaseModel):
    provider: Provider
    key_hint: str
    model: str | None
    verified_at: datetime | None
    created_by: UUID
    updated_at: datetime


class ProviderStatusRead(BaseModel):
    configured: bool
    provider: str | None
    source: Literal["workspace", "server", "fake"] | None


class AIStatusRead(BaseModel):
    workspace_id: UUID
    llm: ProviderStatusRead
    transcription: ProviderStatusRead
    credentials: list[CredentialRead]  # admins only; empty for other roles
    can_manage: bool
