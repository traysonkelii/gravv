from app.ratelimit import TokenBucketLimiter, is_strict


def test_bucket_allows_burst_then_refills() -> None:
    limiter = TokenBucketLimiter(per_minute=60, strict_per_minute=10)
    now = 1000.0
    for _ in range(60):
        assert limiter.allow("u", False, now)[0]
    allowed, wait = limiter.allow("u", False, now)
    assert not allowed and 0 < wait <= 1.0
    assert limiter.allow("u", False, now + 1.0)[0]  # one token per second at 60/min


def test_strict_bucket_is_smaller_and_separate() -> None:
    limiter = TokenBucketLimiter(per_minute=60, strict_per_minute=10)
    now = 0.0
    for _ in range(10):
        assert limiter.allow("u:strict", True, now)[0]
    assert not limiter.allow("u:strict", True, now)[0]
    assert limiter.allow("u", False, now)[0]


def test_strict_paths() -> None:
    assert is_strict("/api/v1/captures/text")
    assert is_strict("/api/v1/contacts/abc/brief")
    assert is_strict("/api/v1/insights/generate")
    assert not is_strict("/api/v1/contacts")


def test_sweep_drops_idle_buckets() -> None:
    limiter = TokenBucketLimiter(60, 10)
    limiter.allow("old", False, 0.0)
    limiter.buckets["old"].updated = -10_000
    limiter.sweep(older_than=600)
    assert "old" not in limiter.buckets
