"""Supabase Storage through the server-side secret key: signed upload and download URLs, existence, download.

Object paths are always <workspace_id>/<user_id>/<uuid>.<ext>; the API computes them, never the client.
"""

from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.errors import Problem

AUDIO_EXTENSIONS = {"audio/webm": "webm", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class SignedUpload:
    url: str
    token: str


def _client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(
        base_url=f"{s.supabase_url}/storage/v1",
        headers={"apikey": s.supabase_secret_key, "Authorization": f"Bearer {s.supabase_secret_key}"},
        timeout=30,
    )


async def create_signed_upload_url(bucket: str, path: str) -> SignedUpload:
    async with _client() as c:
        r = await c.post(f"/object/upload/sign/{bucket}/{path}", json={})
    if r.status_code >= 400:
        raise Problem(502, "storage_error", "Storage unavailable", "The upload could not be prepared. Try again.")
    body = r.json()
    return SignedUpload(url=f"{get_settings().supabase_url}/storage/v1{body['url']}", token=body.get("token", ""))


async def create_signed_download_url(bucket: str, path: str, ttl_seconds: int = 300) -> str:
    async with _client() as c:
        r = await c.post(f"/object/sign/{bucket}/{path}", json={"expiresIn": ttl_seconds})
    if r.status_code >= 400:
        raise Problem(502, "storage_error", "Storage unavailable", "The download link could not be created.")
    return f"{get_settings().supabase_url}/storage/v1{r.json()['signedURL']}"


async def object_size(bucket: str, path: str) -> int | None:
    """Returns the stored size in bytes, or None when the object does not exist."""
    async with _client() as c:
        r = await c.head(f"/object/{bucket}/{path}")
    if r.status_code == 200:
        return int(r.headers.get("content-length", "0"))
    return None


async def download(bucket: str, path: str) -> bytes:
    async with _client() as c:
        r = await c.get(f"/object/{bucket}/{path}")
    r.raise_for_status()
    return r.content


async def delete_object(bucket: str, path: str) -> None:
    async with _client() as c:
        await c.delete(f"/object/{bucket}/{path}")


async def upload_bytes(bucket: str, path: str, data: bytes, content_type: str) -> None:
    """Server-side upload (exports)."""
    async with _client() as c:
        r = await c.post(
            f"/object/{bucket}/{path}", content=data, headers={"Content-Type": content_type, "x-upsert": "true"}
        )
    r.raise_for_status()
