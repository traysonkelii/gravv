import pytest

from app.ai.llm import AnthropicLLM, FakeLLM, OpenAICompatibleLLM
from app.ai.resolve import AIProviderNotConfigured, WorkspaceKey, llm_from, llm_status, transcription_status
from app.ai.transcription import Deepgram, FakeTranscription
from app.config import Settings


def _settings(**over: object) -> Settings:
    return Settings(app_env="staging", llm_provider="anthropic", transcription_provider="openai", **over)  # type: ignore[arg-type]


def test_workspace_key_wins_over_server_key() -> None:
    s = _settings(anthropic_api_key="sk-ant-server")
    keys = {"anthropic": WorkspaceKey("anthropic", "sk-ant-workspace", "claude-sonnet-5")}
    client = llm_from(keys, s)
    assert isinstance(client, AnthropicLLM) and client.model == "claude-sonnet-5"
    assert llm_status(keys, s).source == "workspace"


def test_openai_key_serves_both_llm_and_transcription() -> None:
    s = _settings()
    keys = {"openai": WorkspaceKey("openai", "sk-workspace", None)}
    assert isinstance(llm_from(keys, s), OpenAICompatibleLLM)
    assert transcription_status(keys, s).provider == "openai"
    keys["deepgram"] = WorkspaceKey("deepgram", "d" * 32, None)
    assert transcription_status(keys, s).provider == "deepgram"
    from app.ai.resolve import transcription_from

    assert isinstance(transcription_from(keys, s), Deepgram)


def test_no_key_anywhere_raises_in_hosted_environments() -> None:
    s = _settings()
    assert not llm_status({}, s).configured
    with pytest.raises(AIProviderNotConfigured):
        llm_from({}, s)


def test_fake_only_when_server_configured_for_it() -> None:
    s = Settings(app_env="local", llm_provider="fake", transcription_provider="fake")
    assert isinstance(llm_from({}, s), FakeLLM)
    from app.ai.resolve import transcription_from

    assert isinstance(transcription_from({}, s), FakeTranscription)
