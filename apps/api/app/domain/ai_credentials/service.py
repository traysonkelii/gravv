from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import crypto
from app.ai.resolve import aad, llm_status, transcription_status
from app.auth.deps import WorkspaceContext
from app.config import get_settings
from app.domain.ai_credentials.schemas import KEY_SHAPES, AIStatusRead, CredentialPut, CredentialRead, ProviderStatusRead
from app.domain.audit import write_audit
from app.errors import Problem

_READ = text(
    "select provider::text, key_hint, model, verified_at, created_by, updated_at from ai_credentials "
    "where workspace_id = :ws order by provider"
)


async def _credentials(session: AsyncSession, ws: WorkspaceContext) -> list[CredentialRead]:
    if not ws.at_least("admin"):
        return []
    rows = (await session.execute(_READ, {"ws": ws.workspace_id})).mappings().all()
    return [CredentialRead(**dict(r)) for r in rows]


async def status(session: AsyncSession, ws: WorkspaceContext) -> AIStatusRead:
    configured = list(await session.scalar(text("select ai_providers_configured(:ws)"), {"ws": ws.workspace_id}) or [])
    keys: dict[str, Any] = dict.fromkeys(configured, True)
    llm = llm_status(keys)
    tr = transcription_status(keys)
    return AIStatusRead(
        workspace_id=ws.workspace_id,
        llm=ProviderStatusRead(configured=llm.configured, provider=llm.provider, source=llm.source),
        transcription=ProviderStatusRead(configured=tr.configured, provider=tr.provider, source=tr.source),
        credentials=await _credentials(session, ws),
        can_manage=ws.at_least("admin"),
    )


async def verify_key(provider: str, api_key: str) -> None:
    """One cheap read-only call per provider. Skipped in the test environment."""
    settings = get_settings()
    if settings.app_env == "test":
        return
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            if provider == "anthropic":
                r = await c.get(
                    "https://api.anthropic.com/v1/models?limit=1", headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}
                )
            elif provider == "openai":
                r = await c.get(f"{settings.openai_base_url.rstrip('/')}/models", headers={"Authorization": f"Bearer {api_key}"})
            else:
                r = await c.get("https://api.deepgram.com/v1/projects", headers={"Authorization": f"Token {api_key}"})
    except httpx.HTTPError as exc:
        raise Problem(
            502,
            "provider_unreachable",
            "Provider unreachable",
            "The provider could not be reached to verify the key. Try again or save without verifying.",
        ) from exc
    if r.status_code in (401, 403):
        raise Problem(422, "invalid_api_key", "Key was rejected", "The provider rejected this key. Check it and try again.")
    if r.status_code >= 400:
        raise Problem(502, "provider_error", "Provider error", f"The provider answered {r.status_code} while verifying the key.")


async def put(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, provider: str, body: CredentialPut) -> CredentialRead:
    if not ws.at_least("admin"):
        raise Problem(403, "insufficient_role", "Insufficient role", "Only admins can manage AI keys.")
    pattern, hint = KEY_SHAPES[provider]
    if not pattern.match(body.api_key):
        raise Problem(422, "invalid_api_key", "Key does not look right", hint + ".")
    if body.verify:
        await verify_key(provider, body.api_key)
    blob = crypto.encrypt(body.api_key, aad(ws.workspace_id, provider))
    row = (
        (
            await session.execute(
                text(
                    "insert into ai_credentials (workspace_id, provider, key_enc, key_hint, model, verified_at, created_by) "
                    "values (:ws, cast(:p as ai_provider), :enc, :hint, :model, case when :verified then now() end, :u) "
                    "on conflict (workspace_id, provider) do update set key_enc = :enc, key_hint = :hint, "
                    "model = :model, verified_at = case when :verified then now() end, created_by = :u "
                    "returning provider::text, key_hint, model, verified_at, created_by, updated_at"
                ),
                {
                    "ws": ws.workspace_id,
                    "p": provider,
                    "enc": blob,
                    "hint": body.api_key[-4:],
                    "model": body.model or None,
                    "verified": body.verify,
                    "u": user_id,
                },
            )
        )
        .mappings()
        .one()
    )
    await write_audit(session, ws.workspace_id, "ai_credential.set", "ai_credential", None, {"provider": provider, "verified": body.verify})
    return CredentialRead(**dict(row))


async def delete(session: AsyncSession, ws: WorkspaceContext, provider: str) -> None:
    if not ws.at_least("admin"):
        raise Problem(403, "insufficient_role", "Insufficient role", "Only admins can manage AI keys.")
    res = await session.execute(
        text("delete from ai_credentials where workspace_id = :ws and provider = cast(:p as ai_provider) returning id"),
        {"ws": ws.workspace_id, "p": provider},
    )
    if res.first() is None:
        raise Problem(404, "not_found", "No key for that provider")
    await write_audit(session, ws.workspace_id, "ai_credential.delete", "ai_credential", None, {"provider": provider})
