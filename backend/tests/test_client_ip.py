from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Enquiry
from tests.conftest import valid_enquiry

URL = "/api/v1/enquiries"


@pytest.fixture
def proxy_hops(monkeypatch: pytest.MonkeyPatch) -> Callable[[int], None]:
    def _set(hops: int) -> None:
        monkeypatch.setattr(get_settings(), "trusted_proxy_hops", hops)

    return _set


async def _stored_ip(session: AsyncSession) -> str:
    session.expire_all()
    row = (
        (await session.execute(select(Enquiry).order_by(Enquiry.created_at.desc())))
        .scalars()
        .first()
    )
    assert row is not None
    return str(row.ip_address)


@pytest.mark.parametrize("header", ["1", "not-an-ip", "999.1.1.1", "<script>", ""])
async def test_garbage_forwarded_header_never_breaks_a_submission(
    client: httpx.AsyncClient, session: AsyncSession, proxy_hops: Callable[[int], None], header: str
) -> None:
    proxy_hops(1)
    res = await client.post(URL, json=valid_enquiry(), headers={"X-Forwarded-For": header})
    assert res.status_code == 201
    assert await _stored_ip(session) == "203.0.113.10"  # falls back to the socket peer


async def test_forwarded_header_ignored_without_trusted_proxies(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await client.post(URL, json=valid_enquiry(), headers={"X-Forwarded-For": "8.8.8.8"})
    assert await _stored_ip(session) == "203.0.113.10"


async def test_only_the_proxy_appended_entry_is_trusted(
    client: httpx.AsyncClient, session: AsyncSession, proxy_hops: Callable[[int], None]
) -> None:
    proxy_hops(1)
    # The client pre-filled "1.1.1.1"; the platform proxy appended the real "198.51.100.7".
    await client.post(
        URL, json=valid_enquiry(), headers={"X-Forwarded-For": "1.1.1.1, 198.51.100.7"}
    )
    assert await _stored_ip(session) == "198.51.100.7"


async def test_spoofed_forwarded_for_cannot_dodge_the_rate_limit(
    client: httpx.AsyncClient, proxy_hops: Callable[[int], None]
) -> None:
    proxy_hops(1)
    statuses = []
    for i in range(6):
        res = await client.post(
            URL,
            json=valid_enquiry(phone=f"98765432{i:02d}"),
            headers={"X-Forwarded-For": f"10.0.0.{i}, 198.51.100.7"},
        )
        statuses.append(res.status_code)
    assert statuses == [201] * 5 + [429]
