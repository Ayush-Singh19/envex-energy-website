import subprocess
import sys
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models import AdminUser, AuditLog
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, BACKEND_DIR, make_client

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


async def _login(client: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await client.post(LOGIN, json={"email": email, "password": password})


async def _admin(session: AsyncSession) -> AdminUser:
    session.expire_all()
    return (
        await session.execute(select(AdminUser).where(AdminUser.email == ADMIN_EMAIL))
    ).scalar_one()


# ---- login ------------------------------------------------------------------------------


async def test_login_sets_hardened_session_cookie(
    client: httpx.AsyncClient, session: AsyncSession, admin_user: AdminUser
) -> None:
    res = await _login(client, ADMIN_EMAIL.upper(), ADMIN_PASSWORD)  # email is case-insensitive
    assert res.status_code == 200
    assert res.json()["full_name"] == "Test Owner"
    assert res.json()["company_name"] == "Envex Energy"

    cookie = res.headers["set-cookie"]
    assert cookie.startswith("envex_admin=")
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Max-Age=28800" in cookie  # 8 hours
    assert "Secure" not in cookie  # only in production (see next test)

    me = await client.get(ME)
    assert me.status_code == 200 and me.json()["email"] == ADMIN_EMAIL

    admin = await _admin(session)
    assert admin.last_login_at is not None
    logins = (await session.execute(select(AuditLog).where(AuditLog.action == "login"))).scalars()
    assert [a.admin_id for a in logins] == [admin.id]


def test_cookie_is_secure_in_production() -> None:
    from fastapi import Response

    from app.api.v1.auth import _set_session_cookie

    response = Response()
    prod = get_settings().model_copy(update={"app_env": "production"})
    _set_session_cookie(response, "token", prod)
    assert "Secure" in response.headers["set-cookie"]


@pytest.mark.parametrize(
    ("email", "password"),
    [(ADMIN_EMAIL, "wrong-password-123"), ("nobody@example.com", ADMIN_PASSWORD)],
)
async def test_bad_credentials_get_the_same_generic_error(
    client: httpx.AsyncClient, admin_user: AdminUser, email: str, password: str
) -> None:
    res = await _login(client, email, password)
    assert res.status_code == 401
    assert res.json() == {
        "error": {"code": "invalid_credentials", "message": "Email or password is incorrect."}
    }
    assert "set-cookie" not in res.headers


async def test_inactive_admin_cannot_log_in(
    client: httpx.AsyncClient, session: AsyncSession, admin_user: AdminUser
) -> None:
    await session.execute(update(AdminUser).values(is_active=False))
    await session.commit()
    assert (await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)).status_code == 401


async def test_account_locks_for_15_minutes_after_5_wrong_passwords(
    client: httpx.AsyncClient, session: AsyncSession, admin_user: AdminUser
) -> None:
    for _ in range(4):
        assert (await _login(client, ADMIN_EMAIL, "nope-nope-nope")).status_code == 401

    fifth = await _login(client, ADMIN_EMAIL, "nope-nope-nope")
    assert fifth.status_code == 423
    assert fifth.json()["error"]["code"] == "account_locked"
    assert "15 minutes" in fifth.json()["error"]["message"]

    # Even the right password is refused while locked.
    assert (await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)).status_code == 423
    admin = await _admin(session)
    assert admin.locked_until is not None
    remaining = admin.locked_until - datetime.now(UTC)
    assert timedelta(minutes=14) < remaining <= timedelta(minutes=15)

    # Once the lock expires, the right password works and the counter resets.
    await session.execute(
        update(AdminUser).values(locked_until=datetime.now(UTC) - timedelta(seconds=1))
    )
    await session.commit()
    assert (await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)).status_code == 200
    admin = await _admin(session)
    assert admin.failed_attempts == 0 and admin.locked_until is None


async def test_successful_login_resets_failed_attempts(
    client: httpx.AsyncClient, session: AsyncSession, admin_user: AdminUser
) -> None:
    for _ in range(3):
        await _login(client, ADMIN_EMAIL, "nope-nope-nope")
    assert (await _admin(session)).failed_attempts == 3
    await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert (await _admin(session)).failed_attempts == 0


async def test_login_is_rate_limited_per_ip(
    client: httpx.AsyncClient, admin_user: AdminUser
) -> None:
    for i in range(10):
        await _login(client, f"x{i}@example.com", "whatever-123")
    res = await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert res.status_code == 429


# ---- session validation -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/admin/today"),
        ("GET", "/api/v1/admin/enquiries"),
        ("GET", "/api/v1/admin/enquiries/export.csv"),
        ("GET", "/api/v1/admin/enquiries/00000000-0000-4000-8000-000000000000"),
        ("PATCH", "/api/v1/admin/enquiries/00000000-0000-4000-8000-000000000000"),
        ("POST", "/api/v1/admin/enquiries/00000000-0000-4000-8000-000000000000/notes"),
        ("POST", "/api/v1/auth/change-password"),
    ],
)
async def test_protected_routes_need_a_session(
    client: httpx.AsyncClient, method: str, path: str
) -> None:
    res = await client.request(method, path, json={})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("kind", ["garbage", "wrong_secret", "expired"])
async def test_invalid_tokens_are_rejected(admin_user: AdminUser, kind: str) -> None:
    settings = get_settings()
    if kind == "garbage":
        token = "not-a-jwt"
    elif kind == "wrong_secret":
        other = settings.model_copy(update={"secret_key": SecretStr("x" * 40)})
        token = create_access_token(str(admin_user.id), other)
    else:
        token = create_access_token(
            str(admin_user.id), settings, now=datetime.now(UTC) - timedelta(hours=9)
        )
    async with make_client("192.0.2.60") as c:
        c.cookies.set("envex_admin", token)
        assert (await c.get(ME)).status_code == 401


async def test_logout_clears_cookie(admin_client: httpx.AsyncClient, session: AsyncSession) -> None:
    res = await admin_client.post("/api/v1/auth/logout")
    assert res.status_code == 204
    assert 'envex_admin=""' in res.headers["set-cookie"] or "Max-Age=0" in res.headers["set-cookie"]
    assert (await admin_client.get(ME)).status_code == 401
    actions = (await session.execute(select(AuditLog.action))).scalars().all()
    assert "logout" in actions


# ---- change password --------------------------------------------------------------------

CHANGE = "/api/v1/auth/change-password"


async def test_change_password_requires_current_password(admin_client: httpx.AsyncClient) -> None:
    res = await admin_client.post(
        CHANGE, json={"current_password": "wrong-one-here", "new_password": "Brand-New-Pass-42"}
    )
    assert res.status_code == 400
    assert "current_password" in res.json()["error"]["fields"]


@pytest.mark.parametrize("weak", ["short", "x" * 80, " leading-space-pass"])
async def test_change_password_rejects_weak_passwords(
    admin_client: httpx.AsyncClient, weak: str
) -> None:
    res = await admin_client.post(
        CHANGE, json={"current_password": ADMIN_PASSWORD, "new_password": weak}
    )
    assert res.status_code == 422
    assert "new_password" in res.json()["error"]["fields"]


async def test_change_password_signs_out_other_sessions(
    admin_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    old_token = admin_client.cookies["envex_admin"]
    # Tokens carry whole-second timestamps; make the old one clearly older.
    await session.execute(
        update(AdminUser).values(password_changed_at=datetime.now(UTC) - timedelta(minutes=5))
    )
    await session.commit()
    old_token = create_access_token(
        str((await _admin(session)).id),
        get_settings(),
        now=datetime.now(UTC) - timedelta(minutes=1),
    )

    res = await admin_client.post(
        CHANGE, json={"current_password": ADMIN_PASSWORD, "new_password": "Brand-New-Pass-42"}
    )
    assert res.status_code == 204
    assert (await admin_client.get(ME)).status_code == 200  # this device got a fresh cookie

    async with make_client("192.0.2.61") as other_device:
        other_device.cookies.set("envex_admin", old_token)
        assert (await other_device.get(ME)).status_code == 401

    async with make_client("192.0.2.62") as c:
        assert (await _login(c, ADMIN_EMAIL, ADMIN_PASSWORD)).status_code == 401
        assert (await _login(c, ADMIN_EMAIL, "Brand-New-Pass-42")).status_code == 200


# ---- create_admin script ----------------------------------------------------------------


async def test_create_or_reset_admin(session: AsyncSession, admin_user: AdminUser) -> None:
    from app.services.auth_service import create_or_reset_admin

    with pytest.raises(ValueError, match="already exists"):
        await create_or_reset_admin(
            session, email=ADMIN_EMAIL, full_name=None, password="Another-Pass-123", reset=False
        )
    with pytest.raises(ValueError, match="at least 12"):
        await create_or_reset_admin(
            session, email="new@example.com", full_name=None, password="short", reset=False
        )

    await session.execute(
        update(AdminUser).values(
            failed_attempts=3, locked_until=datetime.now(UTC) + timedelta(minutes=10)
        )
    )
    await session.commit()
    admin, created = await create_or_reset_admin(
        session, email=ADMIN_EMAIL, full_name=None, password="Reset-Pass-12345", reset=True
    )
    assert created is False
    assert admin.locked_until is None and admin.failed_attempts == 0


def test_create_admin_cli(admin_user: AdminUser) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.scripts.create_admin",
            "--email",
            "Cli@Example.com",
            "--name",
            "Cli User",
            "--password-stdin",
        ],
        input="Cli-Password-2026\n",
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Created admin cli@example.com (Cli User)." in result.stdout
    assert "Cli-Password-2026" not in result.stdout + result.stderr
