import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser, AuditLog, ClickEvent, Enquiry
from tests.conftest import make_enquiry

BASE = "/api/v1/admin"
IST = ZoneInfo("Asia/Kolkata")


def _today() -> "datetime.date":  # type: ignore[name-defined]
    return datetime.now(IST).date()


async def _audit(session: AsyncSession, action: str) -> list[AuditLog]:
    session.expire_all()
    stmt = select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)
    return list((await session.execute(stmt)).scalars())


# ---- list & search ----------------------------------------------------------------------


async def test_list_newest_first_hides_not_relevant_and_counts(
    admin_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    await make_enquiry(session, name="Old", created_at=now - timedelta(days=2))
    await make_enquiry(session, name="Mid", status="called", created_at=now - timedelta(days=1))
    await make_enquiry(session, name="Newest", created_at=now)
    await make_enquiry(session, name="Junk", status="not_relevant")

    res = await admin_client.get(f"{BASE}/enquiries")
    assert res.status_code == 200
    body = res.json()
    assert [i["name"] for i in body["items"]] == ["Newest", "Mid", "Old"]
    assert body["total"] == 3
    assert body["counts"]["all"] == 3
    assert body["counts"]["new"] == 2
    assert body["counts"]["called"] == 1
    assert body["counts"]["not_relevant"] == 1
    assert body["counts"]["site_visit"] == 0

    junk = (await admin_client.get(f"{BASE}/enquiries?status=not_relevant")).json()
    assert [i["name"] for i in junk["items"]] == ["Junk"]


async def test_items_carry_ready_contact_links_and_no_tracking_fields(
    admin_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    e = await make_enquiry(
        session,
        name="Meenakshi Bisht",
        project_type="Hybrid solar",
        utm_source="google",
        ip_address="203.0.113.9",
    )
    item = (await admin_client.get(f"{BASE}/enquiries")).json()["items"][0]

    assert item["tel_url"] == "tel:+919876543210"
    assert item["whatsapp_url"].startswith("https://wa.me/919876543210?text=")
    text = parse_qs(urlsplit(item["whatsapp_url"]).query)["text"][0]
    assert text.startswith("Hello Meenakshi, this is Envex Energy about your hybrid solar enquiry")
    assert f"(ENV-{e.id.hex[:4].upper()})" in text
    assert item["mailto_url"].startswith("mailto:asha@example.com?subject=")
    for hidden in ("utm_source", "utm_medium", "ip_address", "user_agent", "consent"):
        assert hidden not in item


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("harpreet", ["Harpreet Singh"]),
        ("COLD STORAGE", ["Harpreet Singh"]),  # company, case-insensitive
        ("43210", ["Asha Rawat"]),  # phone digits
        ("98765 43210", ["Asha Rawat"]),  # phone as typed with a space
        ("selaqui", ["Harpreet Singh"]),  # location
        ("asha@", ["Asha Rawat"]),  # email
        ("%", []),  # LIKE wildcards are escaped, not "match everything"
        ("_", []),
    ],
)
async def test_search(
    admin_client: httpx.AsyncClient, session: AsyncSession, q: str, expected: list[str]
) -> None:
    await make_enquiry(session)
    await make_enquiry(
        session,
        name="Harpreet Singh",
        company="Singh Cold Storage",
        phone="+919897654321",
        email="hs@example.org",
        location="Selaqui, Dehradun",
    )
    res = await admin_client.get(f"{BASE}/enquiries", params={"q": q})
    assert [i["name"] for i in res.json()["items"]] == expected


async def test_pagination(admin_client: httpx.AsyncClient, session: AsyncSession) -> None:
    now = datetime.now(UTC)
    for i in range(5):
        await make_enquiry(session, name=f"Lead {i}", created_at=now - timedelta(minutes=i))
    page2 = (await admin_client.get(f"{BASE}/enquiries?page=2&page_size=2")).json()
    assert [i["name"] for i in page2["items"]] == ["Lead 2", "Lead 3"]
    assert page2["total"] == 5
    assert (await admin_client.get(f"{BASE}/enquiries?page_size=500")).status_code == 422


# ---- detail -----------------------------------------------------------------------------


async def test_detail_links_repeat_enquiries(
    admin_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    first = await make_enquiry(session, created_at=datetime.now(UTC) - timedelta(hours=2))
    repeat = await make_enquiry(session, is_duplicate=True, duplicate_of=first.id)

    first_detail = (await admin_client.get(f"{BASE}/enquiries/{first.id}")).json()
    assert first_detail["newer"]["id"] == str(repeat.id)
    assert first_detail["original"] is None
    assert first_detail["history"][-1]["text"] == "Enquiry received from the website"

    repeat_detail = (await admin_client.get(f"{BASE}/enquiries/{repeat.id}")).json()
    assert repeat_detail["original"]["id"] == str(first.id)
    assert repeat_detail["history"][-1]["text"] == "Repeat enquiry received from the website"


async def test_detail_errors(admin_client: httpx.AsyncClient) -> None:
    missing = await admin_client.get(f"{BASE}/enquiries/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert (await admin_client.get(f"{BASE}/enquiries/not-a-uuid")).status_code == 422


# ---- updates & audit --------------------------------------------------------------------


async def test_status_change_is_audited_with_old_and_new(
    admin_client: httpx.AsyncClient, session: AsyncSession, admin_user: AdminUser
) -> None:
    e = await make_enquiry(session)
    enquiry_id, admin_id = e.id, admin_user.id
    res = await admin_client.patch(f"{BASE}/enquiries/{enquiry_id}", json={"status": "quote_sent"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "quote_sent"
    assert body["history"][0]["text"] == "Status changed from New to Quote sent"
    assert body["history"][0]["by"] == "Test Owner"

    [entry] = await _audit(session, "update")
    assert entry.admin_id == admin_id
    assert entry.entity_type == "enquiry" and entry.entity_id == enquiry_id
    assert entry.old_value == {"status": "new"}
    assert entry.new_value == {"status": "quote_sent"}
    assert str(entry.ip_address) == "192.0.2.50"

    session.expire_all()
    row = (await session.execute(select(Enquiry).where(Enquiry.id == enquiry_id))).scalar_one()
    assert row.status_changed_at is not None


async def test_follow_up_set_and_clear(
    admin_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    e = await make_enquiry(session)
    url = f"{BASE}/enquiries/{e.id}"

    set_res = await admin_client.patch(url, json={"follow_up_date": "2026-10-02"})
    assert set_res.json()["follow_up_date"] == "2026-10-02"
    assert set_res.json()["history"][0]["text"] == "Follow-up set for 2 Oct 2026"

    # Status-only PATCH must not touch the date.
    await admin_client.patch(url, json={"status": "called"})
    assert (await admin_client.get(url)).json()["follow_up_date"] == "2026-10-02"

    clear = await admin_client.patch(url, json={"follow_up_date": None})
    assert clear.json()["follow_up_date"] is None
    assert clear.json()["history"][0]["text"] == "Follow-up cleared"

    entries = await _audit(session, "update")
    assert [x.new_value for x in entries] == [
        {"follow_up_date": "2026-10-02"},
        {"status": "called"},
        {"follow_up_date": None},
    ]


async def test_noop_patch_writes_no_audit(
    admin_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    e = await make_enquiry(session)
    assert (
        await admin_client.patch(f"{BASE}/enquiries/{e.id}", json={"status": "new"})
    ).status_code == 200
    assert (await admin_client.patch(f"{BASE}/enquiries/{e.id}", json={})).status_code == 200
    assert await _audit(session, "update") == []


async def test_invalid_status_rejected(
    admin_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    e = await make_enquiry(session)
    res = await admin_client.patch(f"{BASE}/enquiries/{e.id}", json={"status": "spam"})
    assert res.status_code == 422
    assert "status" in res.json()["error"]["fields"]


async def test_notes(admin_client: httpx.AsyncClient, session: AsyncSession) -> None:
    e = await make_enquiry(session)
    url = f"{BASE}/enquiries/{e.id}/notes"

    res = await admin_client.post(url, json={"note": "  Called, wants a quote with battery.  "})
    assert res.status_code == 201
    [note] = res.json()["notes"]
    assert note["note"] == "Called, wants a quote with battery."
    assert note["admin_name"] == "Test Owner"
    assert res.json()["history"][0]["text"] == "Note added"

    assert (await admin_client.post(url, json={"note": "   "})).status_code == 422
    assert (await admin_client.post(url, json={"note": "x" * 2001})).status_code == 422

    [entry] = await _audit(session, "add_note")
    assert "Called" not in str(entry.new_value)  # note text stays out of the audit log


# ---- today ------------------------------------------------------------------------------


async def test_today_screen(admin_client: httpx.AsyncClient, session: AsyncSession) -> None:
    now = datetime.now(UTC)
    today = _today()
    await make_enquiry(session, name="Waiting long", created_at=now - timedelta(hours=5))
    await make_enquiry(session, name="Waiting short", created_at=now - timedelta(minutes=10))
    await make_enquiry(
        session, name="Overdue", status="called", follow_up_date=today - timedelta(days=2)
    )
    await make_enquiry(session, name="Due today", status="site_visit", follow_up_date=today)
    await make_enquiry(
        session, name="Later", status="called", follow_up_date=today + timedelta(days=3)
    )
    await make_enquiry(
        session, name="Closed", status="lost", follow_up_date=today - timedelta(days=1)
    )
    await make_enquiry(session, name="Quoted", status="quote_sent")
    await make_enquiry(session, name="Won now", status="won", status_changed_at=now)
    await make_enquiry(
        session,
        name="Won long ago",
        status="won",
        status_changed_at=now - timedelta(days=62),
        created_at=now - timedelta(days=70),
    )
    await make_enquiry(session, name="Old junk", status="not_relevant")
    for kind in ("call", "call", "whatsapp", "quote"):
        session.add(ClickEvent(type=kind))
    session.add(ClickEvent(type="call", created_at=now - timedelta(days=10)))
    await session.commit()

    t = (await admin_client.get(f"{BASE}/today")).json()
    assert t["kpis"]["waiting_for_call"] == 2
    assert t["kpis"]["quotes_out"] == 1
    assert t["kpis"]["won_this_month"] == 1
    assert t["kpis"]["new_this_week"] == 8  # excludes "Won long ago" and not_relevant
    assert t["kpis"]["month_label"] == f"{datetime.now(IST):%B}"
    assert [i["name"] for i in t["call_first"]] == ["Waiting long", "Waiting short"]
    assert [i["name"] for i in t["follow_ups"]] == ["Overdue", "Due today"]
    assert t["later_this_week"] == 1
    assert t["clicks_this_week"] == {"call": 2, "whatsapp": 1, "quote": 1, "email": 0}


# ---- export -----------------------------------------------------------------------------


async def test_csv_export(admin_client: httpx.AsyncClient, session: AsyncSession) -> None:
    first = await make_enquiry(session, created_at=datetime.now(UTC) - timedelta(hours=1))
    await make_enquiry(
        session,
        name='=HYPERLINK("http://evil")',
        message="-2+3",
        status="quote_sent",
        is_duplicate=True,
        duplicate_of=first.id,
    )
    await admin_client.post(f"{BASE}/enquiries/{first.id}/notes", json={"note": "Site looks good"})

    res = await admin_client.get(f"{BASE}/enquiries/export.csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert 'filename="envex-leads-' in res.headers["content-disposition"]
    assert res.text.startswith("﻿")

    rows = list(csv.reader(io.StringIO(res.text.lstrip("﻿"))))
    header, data = rows[0], rows[1:]
    assert header[:3] == ["Reference", "Received", "Name"]
    assert len(data) == 2
    newest, oldest = (dict(zip(header, r, strict=True)) for r in data)
    assert newest["Name"] == '\'=HYPERLINK("http://evil")'  # neutralised formula
    assert newest["Message"] == "'-2+3"
    assert newest["Status"] == "Quote sent"
    assert newest["Repeat of"] == f"ENV-{first.id.hex[:4].upper()}"
    assert oldest["Phone"] == "'+919876543210"  # leading + would be read as a formula
    assert oldest["Latest note"] == "Site looks good"

    [entry] = await _audit(session, "export")
    assert entry.entity_type == "enquiry"


# ---- admin page -------------------------------------------------------------------------


async def test_admin_page_served_with_csp(client: httpx.AsyncClient) -> None:
    res = await client.get("/admin/")
    assert res.status_code == 200
    assert "<title>Envex Leads</title>" in res.text
    csp = res.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp
    assert res.headers["x-frame-options"] == "DENY"

    js = await client.get("/admin/admin.js")
    assert js.status_code == 200 and "innerHTML = ICONS[name]" in js.text

    root = await client.get("/", follow_redirects=False)
    assert root.status_code in (302, 307) and root.headers["location"] == "/admin/"
