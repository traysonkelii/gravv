"""LLM providers behind one protocol: Anthropic (structured outputs through messages.parse), an OpenAI-compatible
HTTP provider (json_schema response format), and a deterministic fake for tests and local development.

Every call returns a validated Pydantic object plus usage so the worker can enforce the daily token budget."""

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import httpx
import structlog
from pydantic import BaseModel, ValidationError

from app.ai import fake
from app.ai.prompts import Prompt
from app.config import Settings, get_settings

log = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

ANTHROPIC_DEFAULT_MODEL = "claude-opus-5"
OPENAI_DEFAULT_MODEL = "gpt-4o"


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class Structured[V]:
    value: V
    usage: Usage
    model: str


class LLMError(RuntimeError):
    """Provider returned something unusable (refusal, invalid structure after retry)."""


class LLMClient(Protocol):
    name: str
    model: str

    async def complete_structured(self, *, prompt: Prompt, schema: type[T], max_tokens: int = 4096) -> Structured[T]: ...

    async def complete_text(self, *, prompt: Prompt, max_tokens: int = 2048) -> Structured[str]: ...


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        import anthropic

        self.client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=2, timeout=120.0)
        self.model = model or ANTHROPIC_DEFAULT_MODEL

    async def complete_structured(self, *, prompt: Prompt, schema: type[T], max_tokens: int = 4096) -> Structured[T]:
        from anthropic.types import MessageParam

        messages: list[MessageParam] = [{"role": "user", "content": prompt.user}]
        last_error: Exception | None = None
        for attempt in range(2):
            response = await self.client.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=prompt.system,
                messages=messages,
                output_format=schema,
            )
            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                raise LLMError(f"model declined the request ({getattr(details, 'category', None)})")
            usage = Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
            parsed = response.parsed_output
            if parsed is not None:
                try:
                    return Structured(value=schema.model_validate(parsed), usage=usage, model=response.model)
                except ValidationError as exc:
                    last_error = exc
            text = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text")
            try:
                return Structured(value=schema.model_validate_json(text), usage=usage, model=response.model)
            except ValidationError as exc:
                last_error = exc
                if attempt == 0:
                    messages.append({"role": "assistant", "content": text or "{}"})
                    messages.append({"role": "user", "content": f"That output did not validate: {exc}. Return only a valid object."})
        raise LLMError(f"structured output failed validation twice: {last_error}")

    async def complete_text(self, *, prompt: Prompt, max_tokens: int = 2048) -> Structured[str]:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=prompt.system,
            messages=[{"role": "user", "content": prompt.user}],
        )
        if response.stop_reason == "refusal":
            raise LLMError("model declined the request")
        text = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text")
        return Structured(value=text, usage=Usage(response.usage.input_tokens, response.usage.output_tokens), model=response.model)


class OpenAICompatibleLLM:
    """Kept for provider redundancy. Any server that speaks the chat completions shape with json_schema works."""

    name = "openai"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.key = api_key
        self.model = model or OPENAI_DEFAULT_MODEL

    async def _chat(self, body: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{self.base_url}/chat/completions", json=body, headers={"Authorization": f"Bearer {self.key}"})
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    async def complete_structured(self, *, prompt: Prompt, schema: type[T], max_tokens: int = 4096) -> Structured[T]:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": prompt.system}, {"role": "user", "content": prompt.user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            },
        }
        data = await self._chat(body)
        content = data["choices"][0]["message"]["content"]
        try:
            value = schema.model_validate_json(content)
        except ValidationError as exc:
            raise LLMError(f"structured output failed validation: {exc}") from exc
        usage = data.get("usage", {})
        return Structured(
            value=value,
            usage=Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
            model=data.get("model", self.model),
        )

    async def complete_text(self, *, prompt: Prompt, max_tokens: int = 2048) -> Structured[str]:
        data = await self._chat(
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": prompt.system}, {"role": "user", "content": prompt.user}],
            }
        )
        usage = data.get("usage", {})
        return Structured(
            value=data["choices"][0]["message"]["content"],
            usage=Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
            model=data.get("model", self.model),
        )


class FakeLLM:
    name = "fake"
    model = "fake-v1"

    async def complete_structured(self, *, prompt: Prompt, schema: type[T], max_tokens: int = 4096) -> Structured[T]:
        value = fake.fake_structured(prompt, schema)
        return Structured(value=value, usage=Usage(len(prompt.user) // 4, 200), model=self.model)

    async def complete_text(self, *, prompt: Prompt, max_tokens: int = 2048) -> Structured[str]:
        if prompt.name == "brief":
            return Structured(value=fake.fake_brief(prompt).text, usage=Usage(len(prompt.user) // 4, 150), model=self.model)
        return Structured(value=prompt.user[:max_tokens], usage=Usage(len(prompt.user) // 4, 50), model=self.model)


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """Server-wide provider from environment keys (no workspace key). Jobs use app.ai.resolve instead."""
    s = settings or get_settings()
    if s.llm_provider == "anthropic" and s.anthropic_api_key:
        return AnthropicLLM(api_key=s.anthropic_api_key, model=s.llm_model or None)
    if s.llm_provider == "openai" and s.openai_api_key:
        return OpenAICompatibleLLM(api_key=s.openai_api_key, base_url=s.openai_base_url, model=s.llm_model or None)
    if s.llm_provider != "fake":
        log.warning("llm_provider_missing_key", provider=s.llm_provider, using="fake")
    return FakeLLM()
