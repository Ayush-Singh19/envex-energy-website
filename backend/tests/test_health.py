import httpx


async def test_health_reports_db_ok(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "ok"}


async def test_health_answers_head_for_uptime_monitors(client: httpx.AsyncClient) -> None:
    res = await client.head("/api/v1/health")
    assert res.status_code == 200


async def test_security_headers_present(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["x-content-type-options"] == "nosniff"
    # CSP is scoped to the admin UI; HSTS only in production.
    assert "content-security-policy" not in res.headers
    assert "strict-transport-security" not in res.headers


async def test_request_id_generated_and_echoed(client: httpx.AsyncClient) -> None:
    generated = await client.get("/api/v1/health")
    assert len(generated.headers["x-request-id"]) == 32

    echoed = await client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"

    # Junk IDs are replaced rather than reflected into logs/headers.
    junk = await client.get("/api/v1/health", headers={"X-Request-ID": "<script>"})
    assert junk.headers["x-request-id"] != "<script>"


async def test_unknown_route_uses_error_shape(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "not_found", "message": "Not Found"}}


async def test_cors_allows_frontend_only(client: httpx.AsyncClient) -> None:
    ok = await client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5500", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5500"

    # The frontend README serves the site on 127.0.0.1:8080; allowed outside production.
    readme_port = await client.options(
        "/api/v1/enquiries",
        headers={"Origin": "http://127.0.0.1:8080", "Access-Control-Request-Method": "POST"},
    )
    assert readme_port.headers.get("access-control-allow-origin") == "http://127.0.0.1:8080"

    bad = await client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers


def test_dev_origins_are_not_allowed_in_production() -> None:
    from app.core.config import get_settings

    prod = get_settings().model_copy(update={"app_env": "production"})
    assert prod.cors_origins == [prod.frontend_url]
