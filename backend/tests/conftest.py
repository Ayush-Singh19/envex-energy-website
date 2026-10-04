"""Test harness.

Runs against a real PostgreSQL database named ``*_test`` (TEST_DATABASE_URL). The schema
is dropped and rebuilt with Alembic once per session, and every table is truncated
before each test, so tests are independent and the migration itself is exercised.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

# Settings must be in place before any app module is imported.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://envex:envex@localhost:5432/envex_test"
)
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256-signing",
        "FRONTEND_URL": "http://localhost:5500",
        "COMPANY_NAME": "Envex Energy",
        "WHATSAPP_NUMBER": "917055444005",
        "CALL_NUMBER": "+917055444005",
        "ALT_CALL_NUMBER": "+917055444002",
        "ALERT_EMAIL": "alerts@example.com",
        "COMPANY_ADDRESS": "Clement Town, Dehradun, Uttarakhand 248002",
        "SMTP_HOST": "",
        "RATE_LIMIT_ENQUIRY": "5/10minutes",
        "RATE_LIMIT_EVENTS": "60/minute",
        "RATE_LIMIT_STORAGE": "memory://",
        "DUPLICATE_WINDOW_HOURS": "24",
        "SENTRY_DSN": "",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from alembic import command  # noqa: E402

if not TEST_DATABASE_URL.rsplit("/", 1)[-1].endswith("_test"):
    raise RuntimeError("Refusing to run: TEST_DATABASE_URL must point at a *_test database.")

BACKEND_DIR = Path(__file__).resolve().parents[1]


async def _reset_schema() -> None:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> None:
    """Fresh schema via the real migrations (sync: runs before the test event loop)."""
    asyncio.run(_reset_schema())
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    from app.db.session import engine

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE enquiry_notes, audit_log, click_events, enquiries, admin_users "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    from app.db.session import SessionLocal

    async with SessionLocal() as s:
        yield s


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with make_client("203.0.113.10") as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    from app.core.rate_limit import limiter

    limiter.reset()


@pytest.fixture
def override_settings() -> Iterator[Callable[..., None]]:
    """Swap selected settings for one test, e.g. ``override_settings(smtp_host="x")``."""
    from app.core.config import get_settings
    from app.main import app

    def _apply(**changes: object) -> None:
        patched = get_settings().model_copy(update=changes)
        app.dependency_overrides[get_settings] = lambda: patched

    yield _apply
    app.dependency_overrides.pop(get_settings, None)


def make_client(ip: str) -> httpx.AsyncClient:
    from app.main import app

    transport = httpx.ASGITransport(app=app, client=(ip, 51000))
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def valid_enquiry(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Asha Rawat",
        "company": "Rawat Cold Storage",
        "phone": "98765 43210",
        "email": "asha@example.com",
        "location": "Dehradun",
        "project_type": "Rooftop solar",
        "system_size": "5 kW",
        "message": "Roof is about 800 sq ft, south facing.",
        "consent": True,
        "website": "",
        "source_page": "/",
    }
    payload.update(overrides)
    return payload


# ---- admin fixtures ---------------------------------------------------------------------

ADMIN_EMAIL = "owner@example.com"
ADMIN_PASSWORD = "Correct-Horse-Battery-9"  # test-only


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    # Production uses 12 rounds; 4 keeps the suite quick while exercising the same code.
    monkeypatch.setattr("app.core.security.BCRYPT_ROUNDS", 4)


@pytest.fixture
async def admin_user(session: AsyncSession) -> Any:
    from app.services.auth_service import create_or_reset_admin

    admin, _ = await create_or_reset_admin(
        session, email=ADMIN_EMAIL, full_name="Test Owner", password=ADMIN_PASSWORD, reset=False
    )
    # An admin who has already replaced the seed password. The forced first-login
    # change has its own tests (seed_admin fixture).
    admin.must_change_password = False
    await session.commit()
    return admin


@pytest.fixture
async def seed_admin(session: AsyncSession) -> Any:
    """Freshly created from the CLI: must change the seed password before anything else."""
    from app.services.auth_service import create_or_reset_admin

    admin, _ = await create_or_reset_admin(
        session, email=ADMIN_EMAIL, full_name="Test Owner", password=ADMIN_PASSWORD, reset=False
    )
    return admin


@pytest.fixture
async def admin_client(admin_user: Any) -> AsyncIterator[httpx.AsyncClient]:
    async with make_client("192.0.2.50") as c:
        res = await c.post(
            "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert res.status_code == 200, res.text
        yield c


async def make_enquiry(session: AsyncSession, **overrides: Any) -> Any:
    """Insert an enquiry directly (bypasses the public rate limit)."""
    import uuid as _uuid

    from app.models import Enquiry

    fields: dict[str, Any] = {
        "id": _uuid.uuid4(),
        "name": "Asha Rawat",
        "phone": "+919876543210",
        "email": "asha@example.com",
        "location": "Dehradun",
        "project_type": "Rooftop solar",
        "consent": True,
    }
    fields.update(overrides)
    enquiry = Enquiry(**fields)
    session.add(enquiry)
    await session.commit()
    return enquiry
