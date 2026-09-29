"""Which provider serves a workspace. Order: the workspace's own key, then a server-wide key the operator may
have configured, then the deterministic fake when the server is configured for it. Nothing else."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import crypto
from app.ai.llm import AnthropicLLM, FakeLLM, LLMClient, OpenAICompatibleLLM
from app.ai.transcription import Deepgram, FakeTranscription, OpenAIWhisper, TranscriptionClient
from app.config import Settings, get_settings

Source = str  # workspace | server | fake


@dataclass(frozen=True)
class WorkspaceKey:
    provider: str
    api_key: str
    model: str | None


@dataclass(frozen=True)
class ProviderStatus:
    configured: bool
    provider: str | None
    source: Source | None


class AIProviderNotConfigured(RuntimeError):
    message = "No AI provider is configured for this workspace. An admin can add an API key under Settings, AI."


def aad(workspace_id: UUID | str, provider: str) -> str:
    return f"ai_credentials:{workspace_id}:{provider}"


async def load_workspace_keys(session: AsyncSession, workspace_id: UUID | str) -> dict[str, WorkspaceKey]:
    """Worker-side (service_role): decrypts the workspace's provider keys."""
    rows = (
        await session.execute(
            text("select provider::text, key_enc, model from ai_credentials where workspace_id = :ws"), {"ws": workspace_id}
        )
    ).all()
    out: dict[str, WorkspaceKey] = {}
    for provider, blob, model in rows:
        out[provider] = WorkspaceKey(provider=provider, api_key=crypto.decrypt(blob, aad(workspace_id, provider)), model=model)
    return out


def llm_status(keys: dict[str, Any], settings: Settings | None = None) -> ProviderStatus:
    s = settings or get_settings()
    if "anthropic" in keys:
        return ProviderStatus(True, "anthropic", "workspace")
    if "openai" in keys:
        return ProviderStatus(True, "openai", "workspace")
    if s.llm_provider == "anthropic" and s.anthropic_api_key:
        return ProviderStatus(True, "anthropic", "server")
    if s.llm_provider == "openai" and s.openai_api_key:
        return ProviderStatus(True, "openai", "server")
    if s.llm_provider == "fake":
        return ProviderStatus(True, "fake", "fake")
    return ProviderStatus(False, None, None)


def transcription_status(keys: dict[str, Any], settings: Settings | None = None) -> ProviderStatus:
    s = settings or get_settings()
    if "deepgram" in keys:
        return ProviderStatus(True, "deepgram", "workspace")
    if "openai" in keys:
        return ProviderStatus(True, "openai", "workspace")
    if s.transcription_provider == "deepgram" and s.deepgram_api_key:
        return ProviderStatus(True, "deepgram", "server")
    if s.transcription_provider == "openai" and s.openai_api_key:
        return ProviderStatus(True, "openai", "server")
    if s.transcription_provider == "fake":
        return ProviderStatus(True, "fake", "fake")
    return ProviderStatus(False, None, None)


def llm_from(keys: dict[str, WorkspaceKey], settings: Settings | None = None) -> LLMClient:
    s = settings or get_settings()
    status = llm_status(keys, s)
    if not status.configured:
        raise AIProviderNotConfigured(AIProviderNotConfigured.message)
    if status.source == "workspace":
        k = keys[status.provider or ""]
        if k.provider == "anthropic":
            return AnthropicLLM(api_key=k.api_key, model=k.model or s.llm_model or None)
        return OpenAICompatibleLLM(api_key=k.api_key, base_url=s.openai_base_url, model=k.model or s.llm_model or None)
    if status.source == "server":
        if status.provider == "anthropic":
            return AnthropicLLM(api_key=s.anthropic_api_key, model=s.llm_model or None)
        return OpenAICompatibleLLM(api_key=s.openai_api_key, base_url=s.openai_base_url, model=s.llm_model or None)
    return FakeLLM()


def transcription_from(keys: dict[str, WorkspaceKey], settings: Settings | None = None) -> TranscriptionClient:
    s = settings or get_settings()
    status = transcription_status(keys, s)
    if not status.configured:
        raise AIProviderNotConfigured(
            "No transcription provider is configured for this workspace. An admin can add an OpenAI or Deepgram key under Settings, AI."
        )
    if status.source == "workspace":
        k = keys[status.provider or ""]
        return Deepgram(api_key=k.api_key) if k.provider == "deepgram" else OpenAIWhisper(api_key=k.api_key)
    if status.source == "server":
        return Deepgram(api_key=s.deepgram_api_key) if status.provider == "deepgram" else OpenAIWhisper(api_key=s.openai_api_key)
    return FakeTranscription()
