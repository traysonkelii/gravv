import httpx

from app.main import create_app


async def test_rate_limited_response_is_problem_json(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app import config

    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    config.get_settings.cache_clear()
    app = create_app()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            statuses = [(await c.get("/api/v1/me")).status_code for _ in range(4)]
            assert statuses[:3] == [401, 401, 401] and statuses[3] == 429
            r = await c.get("/api/v1/me")
            assert r.headers["content-type"].startswith("application/problem+json")
            assert r.headers["retry-after"]
            assert (await c.get("/healthz")).status_code == 200
    finally:
        monkeypatch.delenv("RATE_LIMIT_PER_MINUTE")
        config.get_settings.cache_clear()
