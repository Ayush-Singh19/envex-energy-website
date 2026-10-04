import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Enquiry
from tests.conftest import make_client, valid_enquiry

URL = "/api/v1/enquiries"


async def _count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Enquiry))).scalar_one()


async def _get(session: AsyncSession, enquiry_id: str) -> Enquiry:
    session.expire_all()
    return (
        await session.execute(select(Enquiry).where(Enquiry.id == uuid.UUID(enquiry_id)))
    ).scalar_one()


# ---- happy path -------------------------------------------------------------------------


async def test_valid_enquiry_is_saved_and_returns_whatsapp_link(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    res = await client.post(
        URL,
        json=valid_enquiry(utm_source="google", utm_medium="cpc", utm_campaign="rooftop"),
        headers={"User-Agent": "Mozilla/5.0 " + "x" * 400},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert set(body) == {"id", "whatsapp_url", "message"}

    row = await _get(session, body["id"])
    assert row.phone == "+919876543210"  # normalised to E.164
    assert row.name == "Asha Rawat"
    assert row.project_type == "Rooftop solar"
    assert row.consent is True
    assert row.status == "new"
    assert row.is_duplicate is False and row.duplicate_of is None
    assert (row.utm_source, row.utm_medium, row.utm_campaign) == ("google", "cpc", "rooftop")
    assert row.source_page == "/"
    assert str(row.ip_address) == "203.0.113.10"
    assert row.user_agent is not None and len(row.user_agent) == 300

    url = body["whatsapp_url"]
    assert url.startswith("https://wa.me/917055444005?text=")
    text = parse_qs(urlsplit(url).query)["text"][0]
    assert f"Reference: ENV-{row.id.hex[:4].upper()}" in text
    assert "Project: Rooftop solar (5 kW)" in text


async def test_optional_fields_blank_are_stored_as_null(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    res = await client.post(
        URL, json=valid_enquiry(company="  ", system_size="", message="", source_page=None)
    )
    assert res.status_code == 201
    row = await _get(session, res.json()["id"])
    assert (row.company, row.system_size, row.message, row.source_page) == (None, None, None, None)
    assert (
        "Project: Rooftop solar\n"
        in parse_qs(urlsplit(res.json()["whatsapp_url"]).query)["text"][0]
    )


# ---- validation -------------------------------------------------------------------------


async def test_missing_required_fields_use_frontend_messages(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    res = await client.post(URL, json={"consent": True})
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "validation_error"
    assert err["fields"] == {
        "name": "Please enter your name.",
        "phone": "Please enter a phone number we can reach you on.",
        "email": "Please enter a valid email address.",
        "location": "Please tell us where the project is.",
        "project_type": "Please choose the type of project.",
    }
    assert await _count(session) == 0


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"project_type": "Nuclear"}, "project_type"),
        ({"consent": False}, "consent"),
        ({"email": "not-an-email"}, "email"),
        ({"email": "a b@example.com"}, "email"),
        ({"phone": "12345"}, "phone"),
        ({"phone": "call me maybe"}, "phone"),
        ({"name": "x" * 121}, "name"),
        ({"location": "x" * 161}, "location"),
        ({"message": "x" * 4001}, "message"),
        ({"utm_source": "x" * 101}, "utm_source"),
    ],
)
async def test_invalid_field_is_rejected(
    client: httpx.AsyncClient, session: AsyncSession, overrides: dict[str, Any], field: str
) -> None:
    res = await client.post(URL, json=valid_enquiry(**overrides))
    assert res.status_code == 422
    assert field in res.json()["error"]["fields"]
    assert await _count(session) == 0


async def test_every_frontend_project_type_is_accepted(client: httpx.AsyncClient) -> None:
    from app.core.constants import PROJECT_TYPES

    assert len(PROJECT_TYPES) == 11
    for i, ptype in enumerate(PROJECT_TYPES):
        async with make_client(f"198.51.100.{i + 1}") as c:
            res = await c.post(
                URL, json=valid_enquiry(project_type=ptype, phone=f"98765432{i:02d}")
            )
        assert res.status_code == 201, (ptype, res.text)


async def test_malformed_json_gets_error_shape(client: httpx.AsyncClient) -> None:
    res = await client.post(URL, content=b"{not json", headers={"Content-Type": "application/json"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


# ---- honeypot ---------------------------------------------------------------------------


async def test_honeypot_returns_fake_success_and_stores_nothing(
    client: httpx.AsyncClient, session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    res = await client.post(URL, json=valid_enquiry(website="https://spam.example"))
    assert res.status_code == 201
    body = res.json()
    assert set(body) == {"id", "whatsapp_url", "message"}
    uuid.UUID(body["id"])  # looks real
    assert await _count(session) == 0
    assert not any(r.message.startswith("alert_email") for r in caplog.records)


# ---- duplicates -------------------------------------------------------------------------


async def test_same_phone_within_window_is_flagged_but_stored(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    first = (await client.post(URL, json=valid_enquiry(phone="98765 43210"))).json()
    # Same number written differently still matches after normalisation.
    second = (await client.post(URL, json=valid_enquiry(phone="+91-98765-43210"))).json()
    third = (await client.post(URL, json=valid_enquiry(phone="098765 43210"))).json()
    other = (await client.post(URL, json=valid_enquiry(phone="91234 56789"))).json()

    assert await _count(session) == 4
    first_row = await _get(session, first["id"])
    assert first_row.is_duplicate is False
    root_id = first_row.id

    for dup in (second, third):
        row = await _get(session, dup["id"])
        assert row.is_duplicate is True
        assert row.duplicate_of == root_id  # always points at the root enquiry

    assert (await _get(session, other["id"])).is_duplicate is False


async def test_same_phone_outside_window_is_not_a_duplicate(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    first = (await client.post(URL, json=valid_enquiry())).json()
    await session.execute(
        update(Enquiry)
        .where(Enquiry.id == uuid.UUID(first["id"]))
        .values(created_at=datetime.now(UTC) - timedelta(hours=25))
    )
    await session.commit()

    second = (await client.post(URL, json=valid_enquiry())).json()
    assert (await _get(session, second["id"])).is_duplicate is False


async def test_duplicate_window_zero_disables_detection(
    client: httpx.AsyncClient, session: AsyncSession, override_settings: Callable[..., None]
) -> None:
    override_settings(duplicate_window_hours=0)
    await client.post(URL, json=valid_enquiry())
    second = (await client.post(URL, json=valid_enquiry())).json()
    assert (await _get(session, second["id"])).is_duplicate is False


# ---- rate limiting ----------------------------------------------------------------------


async def test_rate_limit_is_five_per_ten_minutes_per_ip(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    for i in range(5):
        res = await client.post(URL, json=valid_enquiry(phone=f"98765432{i:02d}"))
        assert res.status_code == 201

    blocked = await client.post(URL, json=valid_enquiry(phone="9876543299"))
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert await _count(session) == 5

    async with make_client("198.51.100.77") as other_ip:
        assert (await other_ip.post(URL, json=valid_enquiry())).status_code == 201


# ---- email alert ------------------------------------------------------------------------


async def test_alert_is_logged_not_sent_without_smtp_and_logs_hold_no_pii(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    payload = valid_enquiry(message="Secret roof details")
    res = await client.post(URL, json=payload)
    assert res.status_code == 201

    records = [r for r in caplog.records if r.message == "alert_email_not_sent_smtp_disabled"]
    assert len(records) == 1
    assert records[0].enquiry_id == res.json()["id"]  # type: ignore[attr-defined]

    everything_logged = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    for pii in ("98765", "9876543210", "asha@example.com", "Secret roof details", "Asha Rawat"):
        assert pii not in everything_logged


async def test_alert_email_sent_via_smtp_with_escaped_html(
    client: httpx.AsyncClient,
    override_settings: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[EmailMessage, dict[str, Any]]] = []

    async def fake_send(msg: EmailMessage, **kwargs: Any) -> None:
        sent.append((msg, kwargs))

    monkeypatch.setattr("app.services.notification_service.aiosmtplib.send", fake_send)
    override_settings(smtp_host="smtp.example.com", smtp_port=587, smtp_user="bot@example.com")

    res = await client.post(URL, json=valid_enquiry(name="<script>alert(1)</script>"))
    assert res.status_code == 201

    assert len(sent) == 1
    msg, kwargs = sent[0]
    assert msg["To"] == "alerts@example.com"
    assert msg["Reply-To"] == "asha@example.com"
    assert msg["Subject"].startswith("New enquiry ENV-")
    assert kwargs["hostname"] == "smtp.example.com" and kwargs["start_tls"] is True

    html_part = msg.get_body(preferencelist=("html",))
    assert html_part is not None
    html = html_part.get_content()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


async def test_smtp_failure_does_not_lose_the_enquiry(
    client: httpx.AsyncClient,
    session: AsyncSession,
    override_settings: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def broken_send(*_: Any, **__: Any) -> None:
        raise ConnectionRefusedError("smtp down for asha@example.com")

    monkeypatch.setattr("app.services.notification_service.aiosmtplib.send", broken_send)
    override_settings(smtp_host="smtp.example.com")

    res = await client.post(URL, json=valid_enquiry())
    assert res.status_code == 201
    assert await _count(session) == 1
    failures = [r for r in caplog.records if r.message == "alert_email_failed"]
    assert len(failures) == 1
    assert "asha@example.com" not in str(failures[0].__dict__)
