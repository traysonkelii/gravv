"""Per-user token bucket rate limiting (Section 6.7). In-memory per instance, which is acceptable at App Runner scale;
Section 14 lists the shared limiter for when instance count grows. Keys are the JWT subject when a bearer token is
present (read without verification, only to pick a bucket) or the client address otherwise."""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import Settings

STRICT_PREFIXES = ("/api/v1/captures", "/api/v1/ai")
STRICT_SUFFIXES = ("/brief", "/profile/regenerate", "/insights/generate")


@dataclass
class Bucket:
    tokens: float
    updated: float = field(default_factory=time.monotonic)


class TokenBucketLimiter:
    def __init__(self, per_minute: int, strict_per_minute: int) -> None:
        self.rate = per_minute / 60.0
        self.capacity = float(per_minute)
        self.strict_rate = strict_per_minute / 60.0
        self.strict_capacity = float(strict_per_minute)
        self.buckets: dict[str, Bucket] = {}

    def allow(self, key: str, strict: bool, now: float | None = None) -> tuple[bool, float]:
        """Returns (allowed, seconds until a token is available)."""
        now = now if now is not None else time.monotonic()
        rate = self.strict_rate if strict else self.rate
        capacity = self.strict_capacity if strict else self.capacity
        bucket = self.buckets.get(key)
        if bucket is None:
            bucket = Bucket(tokens=capacity, updated=now)
            self.buckets[key] = bucket
        bucket.tokens = min(capacity, bucket.tokens + (now - bucket.updated) * rate)
        bucket.updated = now
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return True, 0.0
        return False, (1 - bucket.tokens) / rate

    def sweep(self, older_than: float = 600.0) -> None:
        cutoff = time.monotonic() - older_than
        for key in [k for k, b in self.buckets.items() if b.updated < cutoff]:
            del self.buckets[key]


def is_strict(path: str) -> bool:
    return path.startswith(STRICT_PREFIXES) or path.endswith(STRICT_SUFFIXES)


def bucket_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            sub = jwt.decode(auth[7:], options={"verify_signature": False}).get("sub")
            if sub:
                return f"user:{sub}"
        except jwt.PyJWTError:
            pass
    return f"ip:{request.client.host if request.client else 'unknown'}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Callable[..., Awaitable[None]], settings: Settings) -> None:
        super().__init__(app)
        self.limiter = TokenBucketLimiter(settings.rate_limit_per_minute, max(5, settings.rate_limit_per_minute // 6))
        self.enabled = settings.rate_limit_per_minute > 0
        self._requests = 0

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not self.enabled or not request.url.path.startswith("/api/"):
            return await call_next(request)
        strict = is_strict(request.url.path) and request.method in ("POST", "PUT", "PATCH", "DELETE")
        key = bucket_key(request) + (":strict" if strict else "")
        allowed, wait = self.limiter.allow(key, strict)
        self._requests += 1
        if self._requests % 1000 == 0:
            self.limiter.sweep()
        if not allowed:
            body = {
                "type": "https://gravv.app/problems/rate_limited",
                "title": "Too many requests",
                "status": 429,
                "detail": "Slow down and try again in a moment.",
                "instance": request.url.path,
                "request_id": getattr(request.state, "request_id", None),
            }
            return JSONResponse(
                body, status_code=429, media_type="application/problem+json", headers={"Retry-After": str(max(1, int(wait) + 1))}
            )
        return await call_next(request)
