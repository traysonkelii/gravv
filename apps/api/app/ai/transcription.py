"""Transcription providers behind one protocol: OpenAI Whisper API, Deepgram, or a deterministic fake."""

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings, get_settings

WEBM_MAGIC = b"\x1a\x45\xdf\xa3"
WAV_MAGIC = b"RIFF"
MP3_MAGICS = (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    duration_seconds: float | None
    provider: str


class TranscriptionClient(Protocol):
    async def transcribe(self, *, audio: bytes, mime: str, language: str | None) -> Transcript: ...


def sniff_audio(data: bytes, declared_mime: str) -> bool:
    """Content sniffing before any provider call: the declared type must match the bytes."""
    head = data[:16]
    if declared_mime == "audio/webm":
        return head.startswith(WEBM_MAGIC)
    if declared_mime == "audio/mp4":
        return len(head) >= 8 and head[4:8] == b"ftyp"
    if declared_mime == "audio/wav":
        return head.startswith(WAV_MAGIC)
    if declared_mime == "audio/mpeg":
        return any(head.startswith(m) for m in MP3_MAGICS)
    return False


class OpenAIWhisper:
    def __init__(self, settings: Settings) -> None:
        self.key = settings.openai_api_key
        self.model = "whisper-1"

    async def transcribe(self, *, audio: bytes, mime: str, language: str | None) -> Transcript:
        ext = {"audio/webm": "webm", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav"}.get(mime, "webm")
        data = {"model": self.model, "response_format": "verbose_json"}
        if language:
            data["language"] = language
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.key}"},
                files={"file": (f"audio.{ext}", audio, mime)},
                data=data,
            )
        r.raise_for_status()
        body = r.json()
        return Transcript(
            text=body.get("text", "").strip(),
            language=body.get("language"),
            duration_seconds=body.get("duration"),
            provider="openai",
        )


class Deepgram:
    def __init__(self, settings: Settings) -> None:
        self.key = settings.deepgram_api_key

    async def transcribe(self, *, audio: bytes, mime: str, language: str | None) -> Transcript:
        params = {"model": "nova-3", "smart_format": "true", "punctuate": "true"}
        if language:
            params["language"] = language
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                "https://api.deepgram.com/v1/listen",
                params=params,
                content=audio,
                headers={"Authorization": f"Token {self.key}", "Content-Type": mime},
            )
        r.raise_for_status()
        body = r.json()
        alt = body["results"]["channels"][0]["alternatives"][0]
        return Transcript(
            text=alt.get("transcript", "").strip(),
            language=None,
            duration_seconds=body.get("metadata", {}).get("duration"),
            provider="deepgram",
        )


class FakeTranscription:
    """Local and test provider. Audio that is really UTF-8 text is returned verbatim, which lets end-to-end
    tests upload a sentence as a 'recording'. Anything else gets the reference scenario sentence."""

    CANNED = (
        "Update the meeting note with Colonel Johnson. Add that he is a competitive pinball fanatic. "
        "Remind me to contact the program officers he mentioned, and remind me to book the next meeting "
        "at a pinball bar in thirty days."
    )

    async def transcribe(self, *, audio: bytes, mime: str, language: str | None) -> Transcript:
        try:
            text = audio.decode("utf-8")
            if text.isprintable() or "\n" in text:
                return Transcript(text=text.strip(), language="en", duration_seconds=len(text) / 15, provider="fake")
        except UnicodeDecodeError:
            pass
        return Transcript(text=self.CANNED, language="en", duration_seconds=18.0, provider="fake")


def get_transcription_client(settings: Settings | None = None) -> TranscriptionClient:
    s = settings or get_settings()
    if s.transcription_provider == "openai" and s.openai_api_key:
        return OpenAIWhisper(s)
    if s.transcription_provider == "deepgram" and s.deepgram_api_key:
        return Deepgram(s)
    return FakeTranscription()
