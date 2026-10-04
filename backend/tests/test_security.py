"""Checks for the controls in the security doc (Envex_Backend_Security.pdf)."""

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AuditLog, ClickEvent, Enquiry, EnquiryNote
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, make_client, make_enquiry, valid_enquiry

ENQUIRIES = "/api/v1/enquiries"


def _admin_routes() -> list[tuple[str, str]]:
    """Every /admin route the app actually serves, with path params filled in."""
    from app.main import app

    # The OpenAPI schema lists every served path and method (included routers are lazy
    # in this FastAPI version, so app.routes doesn't).
    routes = []
    for path, ops in app.openapi()["paths"].items():
        if path.startswith("/api/v1/admin"):
            filled = path.replace("{enquiry_id}", str(uuid.uuid4()))
            routes.extend((m.upper(), filled) for m in sorted(ops))
    assert len(routes) >= 7, routes  # guard against the discovery silently finding nothing
    return routes


# ---- access control ---------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), _admin_routes())
async def test_every_admin_route_requires_a_session(
    client: httpx.AsyncClient, method: str, path: str
) -> None:
    res = await client.request(method, path, json={})
    assert res.status_code == 401, (method, path, res.status_code)
    assert res.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(("method", "path"), _admin_routes())
async def test_every_admin_route_blocks_a_seed_password(
    seed_admin: object, method: str, path: str
) -> None:
    async with make_client("192.0.2.70") as c:
        await c.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        res = await c.request(method, path, json={})
    assert res.status_code == 403, (method, path, res.status_code)
    assert res.json()["error"]["code"] == "password_change_required"


# ---- input validation -------------------------------------------------------------------


async def test_unknown_enquiry_fields_are_rejected(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    res = await client.post(ENQUIRIES, json=valid_enquiry(status="won", is_duplicate=True))
    assert res.status_code == 422
    assert {"status", "is_duplicate"} <= set(res.json()["error"]["fields"])
    assert (await session.execute(select(func.count()).select_from(Enquiry))).scalar_one() == 0


@pytest.mark.parametrize("consent", ["true", 1, "yes"])
async def test_consent_must_be_a_real_boolean(client: httpx.AsyncClient, consent: object) -> None:
    res = await client.post(ENQUIRIES, json=valid_enquiry(consent=consent))
    assert res.status_code == 422
    assert "consent" in res.json()["error"]["fields"]


async def test_unknown_event_and_patch_fields_are_rejected(admin_client: httpx.AsyncClient) -> None:
    ev = await admin_client.post("/api/v1/events", json={"type": "call", "phone": "98765"})
    assert ev.status_code == 422
    e_id = uuid.uuid4()
    patch = await admin_client.patch(f"/api/v1/admin/enquiries/{e_id}", json={"name": "x"})
    assert patch.status_code == 422


SQLI = [
    "'; DROP TABLE enquiries; --",
    '" OR "1"="1',
    "x' UNION SELECT password_hash FROM admin_users --",
    "Robert'); DELETE FROM admin_users;--",
]


@pytest.mark.parametrize("payload", SQLI)
async def test_sql_injection_is_stored_as_plain_text(
    client: httpx.AsyncClient, admin_client: httpx.AsyncClient, session: AsyncSession, payload: str
) -> None:
    res = await client.post(
        ENQUIRIES, json=valid_enquiry(name=payload[:120], location=payload[:160], message=payload)
    )
    assert res.status_code == 201
    session.expire_all()
    row = (await session.execute(select(Enquiry))).scalar_one()
    assert row.message == payload  # stored verbatim, never executed

    found = await admin_client.get("/api/v1/admin/enquiries", params={"q": payload[:100]})
    assert found.status_code == 200
    # Search as an attack: the query is a bound parameter, so it can only ever match text.
    assert all(i["message"] == payload for i in found.json()["items"])
    assert (await admin_client.get("/api/v1/auth/me")).status_code == 200  # admins table intact


async def test_script_tags_are_returned_as_data_not_markup(
    client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    xss = '<script>alert("x")</script><img src=x onerror=alert(1)>'
    await client.post(ENQUIRIES, json=valid_enquiry(name="Mallory", message=xss))
    res = await admin_client.get("/api/v1/admin/enquiries")
    assert res.headers["content-type"].startswith("application/json")
    assert res.json()["items"][0]["message"] == xss  # JSON data; the UI renders it as text


# ---- request size -----------------------------------------------------------------------


async def test_bodies_over_16kb_are_rejected(client: httpx.AsyncClient) -> None:
    big = valid_enquiry(message="x" * 17_000)
    res = await client.post(ENQUIRIES, json=big)
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "payload_too_large"
    assert res.headers["x-frame-options"] == "DENY"  # still wrapped by the security headers


async def test_streamed_body_without_length_is_also_capped(client: httpx.AsyncClient) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(20):
            yield b"x" * 1024

    res = await client.post(
        ENQUIRIES, content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 413


async def test_a_normal_long_enquiry_still_fits(client: httpx.AsyncClient) -> None:
    # 4,000-character message in Devanagari (3 bytes per character) stays under 16 KB.
    res = await client.post(ENQUIRIES, json=valid_enquiry(message="स" * 4000))
    assert res.status_code == 201


# ---- abuse ------------------------------------------------------------------------------


async def test_enquiry_rate_limit_message_offers_the_phone_number(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    for i in range(5):
        await client.post(ENQUIRIES, json=valid_enquiry(phone=f"98765432{i:02d}"))
    res = await client.post(ENQUIRIES, json=valid_enquiry(phone="9876543299"))
    assert res.status_code == 429
    assert "+91 7055 444 005" in res.json()["error"]["message"]
    [hit] = [r for r in caplog.records if r.message == "rate_limited"]
    assert hit.client == "203.0.113.0"  # type: ignore[attr-defined]  # truncated, not the full IP


# ---- headers, CORS, docs, errors --------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/v1/health", "/admin/", "/api/v1/nope", "/api/v1/auth/me"])
async def test_security_headers_on_every_response(client: httpx.AsyncClient, path: str) -> None:
    res = await client.get(path)
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"


async def test_admin_csp_allows_only_its_own_scripts(client: httpx.AsyncClient) -> None:
    csp = (await client.get("/admin/")).headers["content-security-policy"]
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";"))
    assert directives["script-src"] == "'self'"
    assert directives["frame-ancestors"] == "'none'"
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp


async def test_cors_never_allows_credentials_or_foreign_origins(client: httpx.AsyncClient) -> None:
    res = await client.options(
        ENQUIRIES,
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in res.headers
    ok = await client.options(
        ENQUIRIES,
        headers={"Origin": "http://localhost:5500", "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5500"
    assert "access-control-allow-credentials" not in ok.headers


def _production_settings():
    return get_settings().model_copy(
        update={
            "app_env": "production",
            "secret_key": SecretStr("s" * 90),
            "frontend_url": "https://envexenergy.in",
        }
    )


async def test_production_hides_docs_adds_hsts_and_hides_errors() -> None:
    from app.main import create_app

    prod_app = create_app(_production_settings())

    @prod_app.get("/api/v1/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    transport = httpx.ASGITransport(app=prod_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as c:
        assert (await c.get("/docs")).status_code == 404
        assert (await c.get("/openapi.json")).status_code == 404
        health = await c.get("/api/v1/health")
        assert "max-age=31536000" in health.headers["strict-transport-security"]
        boom_res = await c.get("/api/v1/boom")
    assert boom_res.status_code == 500
    assert boom_res.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong. Please try again."}
    }
    assert "secret internal detail" not in boom_res.text and "Traceback" not in boom_res.text


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"secret_key": SecretStr("short-but-over-32-characters-long-xx")}, "64 random bytes"),
        ({"secret_key": SecretStr("change-me-" + "x" * 90)}, "64 random bytes"),
        ({"frontend_url": "http://envexenergy.in"}, "https://"),
    ],
)
def test_production_refuses_weak_configuration(changes: dict[str, object], message: str) -> None:
    from app.core.config import Settings

    values = _production_settings().model_dump()
    values.update(changes)
    values = {
        k: (v.get_secret_value() if isinstance(v, SecretStr) else v) for k, v in values.items()
    }
    with pytest.raises(ValueError, match=message):
        Settings(**values)


def test_sentry_scrubber_drops_bodies_cookies_and_user() -> None:
    from app.main import _scrub_event

    event = {
        "request": {
            "data": {"phone": "+919876543210"},
            "cookies": {"envex_admin": "jwt"},
            "query_string": "q=asha",
            "headers": {"Cookie": "envex_admin=jwt", "User-Agent": "Mozilla", "X-Request-ID": "r1"},
        },
        "user": {"ip_address": "203.0.113.9"},
    }
    scrubbed = _scrub_event(event, {})
    assert "data" not in scrubbed["request"] and "cookies" not in scrubbed["request"]
    assert "query_string" not in scrubbed["request"] and "user" not in scrubbed
    assert scrubbed["request"]["headers"] == {"User-Agent": "Mozilla", "X-Request-ID": "r1"}


# ---- logging ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ip", "expected"),
    [("203.0.113.57", "203.0.113.0"), ("2001:db8:abcd:12::1", "2001:db8:abcd::"), ("junk", None)],
)
def test_truncate_ip(ip: str, expected: str | None) -> None:
    from app.core.middleware import truncate_ip

    assert truncate_ip(ip) == expected


async def test_request_log_has_truncated_ip_and_no_query_string(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    await client.get("/api/v1/health?email=asha@example.com&phone=9876543210")
    [line] = [r for r in caplog.records if r.message == "request"]
    assert line.client == "203.0.113.0"  # type: ignore[attr-defined]
    assert line.path == "/api/v1/health"  # type: ignore[attr-defined]
    assert "asha@example.com" not in str(line.__dict__) and "9876543210" not in str(line.__dict__)


async def test_admin_actions_never_log_personal_data(
    client: httpx.AsyncClient, admin_client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    created = (await client.post(ENQUIRIES, json=valid_enquiry(message="Secret roof note"))).json()
    url = f"/api/v1/admin/enquiries/{created['id']}"
    await admin_client.get("/api/v1/admin/enquiries", params={"q": "Asha"})
    await admin_client.patch(url, json={"status": "called"})
    await admin_client.post(f"{url}/notes", json={"note": "Customer said 9876543210 is WhatsApp"})
    await admin_client.get("/api/v1/admin/enquiries/export.csv")
    await admin_client.delete(url)
    logged = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    for pii in ("9876543210", "98765 43210", "asha@example.com", "Asha Rawat", "Secret roof note"):
        assert pii not in logged


# ---- deletion on request ----------------------------------------------------------------


async def test_delete_on_request_removes_the_record_and_audits_without_personal_data(
    admin_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    original = await make_enquiry(session, created_at=datetime.now(UTC) - timedelta(hours=1))
    repeat = await make_enquiry(session, is_duplicate=True, duplicate_of=original.id)
    original_id, repeat_id = original.id, repeat.id
    await admin_client.post(
        f"/api/v1/admin/enquiries/{original_id}/notes", json={"note": "call back Monday"}
    )

    res = await admin_client.delete(f"/api/v1/admin/enquiries/{original_id}")
    assert res.status_code == 204
    assert (await admin_client.get(f"/api/v1/admin/enquiries/{original_id}")).status_code == 404
    assert (await admin_client.delete(f"/api/v1/admin/enquiries/{original_id}")).status_code == 404

    session.expire_all()
    notes = (await session.execute(select(func.count()).select_from(EnquiryNote))).scalar_one()
    assert notes == 0  # notes go with it
    survivor = (await session.execute(select(Enquiry).where(Enquiry.id == repeat_id))).scalar_one()
    assert survivor.duplicate_of is None  # the repeat keeps its own data

    [entry] = (
        (await session.execute(select(AuditLog).where(AuditLog.action == "delete"))).scalars().all()
    )
    assert entry.entity_id == original_id
    assert entry.old_value == {"reference": f"ENV-{original_id.hex[:4].upper()}", "status": "new"}
    assert "Asha" not in str(entry.old_value) and "98765" not in str(entry.old_value)


# ---- retention --------------------------------------------------------------------------


async def test_retention_purge(session: AsyncSession) -> None:
    from app.services.retention_service import purge

    now = datetime.now(UTC)
    old = await make_enquiry(session, name="Old lead")
    old_but_active = await make_enquiry(session, name="Old lead with a recent note")
    fresh = await make_enquiry(session, name="Fresh lead")
    old_id, active_id, fresh_id = old.id, old_but_active.id, fresh.id
    long_ago = now - timedelta(days=760)  # ~25 months
    await session.execute(
        update(Enquiry).where(Enquiry.id.in_([old_id, active_id])).values(updated_at=long_ago)
    )
    session.add(EnquiryNote(enquiry_id=active_id, note="still talking", created_at=now))
    session.add(
        AuditLog(action="update", entity_type="enquiry", created_at=now - timedelta(days=400))
    )
    session.add(
        AuditLog(action="update", entity_type="enquiry", created_at=now - timedelta(days=10))
    )
    session.add(ClickEvent(type="call", created_at=now - timedelta(days=400)))
    session.add(ClickEvent(type="call", created_at=now - timedelta(days=10)))
    await session.commit()

    dry = await purge(session, get_settings(), dry_run=True)
    assert (dry.enquiries, dry.audit_entries, dry.click_events) == (1, 1, 1)
    session.expire_all()
    assert (await session.execute(select(func.count()).select_from(Enquiry))).scalar_one() == 3

    result = await purge(session, get_settings())
    assert (result.enquiries, result.audit_entries, result.click_events) == (1, 1, 1)
    session.expire_all()
    remaining = set((await session.execute(select(Enquiry.id))).scalars())
    assert remaining == {active_id, fresh_id}
    assert old_id not in remaining
    [purge_entry] = (
        (await session.execute(select(AuditLog).where(AuditLog.action == "retention_purge")))
        .scalars()
        .all()
    )
    assert purge_entry.new_value == {"enquiries": 1, "audit_entries": 1, "click_events": 1}


async def test_admin_page_is_revalidated_on_every_load(client: httpx.AsyncClient) -> None:
    for path in ("/admin/", "/admin/admin.js", "/admin/admin.css"):
        res = await client.get(path)
        assert res.headers["cache-control"] == "no-cache", path
        assert "etag" in res.headers, path  # unchanged files still come back as a cheap 304
    api = await client.get("/api/v1/auth/me")
    assert api.headers["cache-control"] == "no-store"
