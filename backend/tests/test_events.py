import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClickEvent

URL = "/api/v1/events"


async def _events(session: AsyncSession) -> list[ClickEvent]:
    session.expire_all()
    return list((await session.execute(select(ClickEvent).order_by(ClickEvent.id))).scalars())


async def test_beacon_text_plain_body_is_recorded(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    # navigator.sendBeacon(url, JSON.stringify(...)) sends text/plain.
    res = await client.post(
        URL,
        content=(
            '{"type": "whatsapp", "page": "/?utm_source=x&phone=123#enquiry", "utm_source": "fb"}'
        ),
        headers={"Content-Type": "text/plain;charset=UTF-8"},
    )
    assert res.status_code == 204
    [event] = await _events(session)
    assert event.type == "whatsapp"
    assert event.page == "/"  # query string and fragment dropped
    assert event.utm_source == "fb"


async def test_json_body_also_works(client: httpx.AsyncClient, session: AsyncSession) -> None:
    for kind in ("call", "whatsapp", "quote", "email"):
        assert (await client.post(URL, json={"type": kind})).status_code == 204
    assert [e.type for e in await _events(session)] == ["call", "whatsapp", "quote", "email"]


@pytest.mark.parametrize("body", ['{"type": "sms"}', "{}", "not json", ""])
async def test_invalid_event_rejected(
    client: httpx.AsyncClient, session: AsyncSession, body: str
) -> None:
    res = await client.post(URL, content=body, headers={"Content-Type": "text/plain"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    assert await _events(session) == []


async def test_oversized_event_rejected(client: httpx.AsyncClient) -> None:
    res = await client.post(URL, content='{"type":"call","page":"' + "a" * 3000 + '"}')
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "payload_too_large"


async def test_events_rate_limited_at_sixty_per_minute(client: httpx.AsyncClient) -> None:
    for _ in range(60):
        assert (await client.post(URL, json={"type": "call"})).status_code == 204
    res = await client.post(URL, json={"type": "call"})
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "rate_limited"
