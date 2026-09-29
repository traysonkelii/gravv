"""Supabase JWT verification: JWKS (ES256/RS256) with a cached key set, or HS256 with the project secret."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from app.config import Settings, get_settings
from app.errors import Problem

ASYMMETRIC = {"ES256", "RS256"}


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    email: str
    role: str
    session_id: str | None
    aal: str
    claims: dict[str, Any]


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=600)


def verify_token(token: str, settings: Settings | None = None) -> AuthContext:
    settings = settings or get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise Problem(401, "unauthenticated", "Unauthenticated", "The access token is malformed.") from exc
    alg = header.get("alg")
    try:
        if alg in ASYMMETRIC:
            key = _jwks_client(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json").get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[alg],
                audience="authenticated",
                issuer=settings.auth_issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        elif alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise Problem(401, "unauthenticated", "Unauthenticated", "HS256 tokens are not accepted here.")
            claims = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=settings.auth_issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        else:
            raise Problem(401, "unauthenticated", "Unauthenticated", "Unsupported token algorithm.")
    except jwt.ExpiredSignatureError as exc:
        raise Problem(401, "token_expired", "Session expired", "Sign in again to continue.") from exc
    except jwt.PyJWTError as exc:
        raise Problem(401, "unauthenticated", "Unauthenticated", "The access token could not be verified.") from exc
    return AuthContext(
        user_id=str(claims["sub"]),
        email=str(claims.get("email", "")),
        role=str(claims.get("role", "authenticated")),
        session_id=claims.get("session_id"),
        aal=str(claims.get("aal", "aal1")),
        claims=claims,
    )
