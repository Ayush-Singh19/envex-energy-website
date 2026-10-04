import logging
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
CHANGE = "/api/v1/auth/change-password"
GENERIC = {"error": {"code": "invalid_credentials", "message": "Invalid email or password."}}


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
    body = res.json()
    assert body["full_name"] == "Test Owner" and body["company_name"] == "Envex Energy"
    assert body["must_change_password"] is False

    cookie = res.headers["set-cookie"]
    assert cookie.startswith("envex_admin=")
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=28800" in cookie  # 8 hours
    assert "Secure" not in cookie  # production only (next test)

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


async def test_session_token_carries_only_the_admin_id(
    client: httpx.AsyncClient, admin_user: AdminUser
) -> None:
    import jwt

    await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    claims = jwt.decode(client.cookies["envex_admin"], options={"verify_signature": False})
    assert set(claims) == {"sub", "ver", "typ", "iat", "exp"}
    assert claims["sub"] == str(admin_user.id)
    assert ADMIN_EMAIL not in str(claims)


@pytest.mark.parametrize(
    ("email", "password"),
    [(ADMIN_EMAIL, "wrong-password-123"), ("nobody@example.com", ADMIN_PASSWORD)],
)
async def test_bad_credentials_get_the_same_generic_error(
    client: httpx.AsyncClient, admin_user: AdminUser, email: str, password: str
) -> None:
    res = await _login(client, email, password)
    assert res.status_code == 401
    assert res.json() == GENERIC
    assert "set-cookie" not in res.headers


async def test_inactive_admin_gets_the_generic_error(
    client: httpx.AsyncClient, session: AsyncSession, admin_user: AdminUser
) -> None:
    await session.execute(update(AdminUser).values(is_active=False))
    await session.commit()
    res = await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert res.status_code == 401 and res.json() == GENERIC


async def test_lockout_after_5_failures_for_15_minutes_with_the_same_message(
    client: httpx.AsyncClient, session: AsyncSession, admin_user: AdminUser
) -> None:
    for _ in range(5):
        res = await _login(client, ADMIN_EMAIL, "nope-nope-nope")
        assert res.status_code == 401 and res.json() == GENERIC

    admin = await _admin(session)
    assert admin.locked_until is not None
    remaining = admin.locked_until - datetime.now(UTC)
    assert timedelta(minutes=14) < remaining <= timedelta(minutes=15)

    # While locked, even the right password gets the identical response: the endpoint
    # never reveals that this account exists or is locked.
    locked = await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert locked.status_code == 401 and locked.json() == GENERIC
    assert "set-cookie" not in locked.headers

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


async def test_passwords_never_reach_the_logs(
    client: httpx.AsyncClient, admin_user: AdminUser, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    await _login(client, ADMIN_EMAIL, "Wrong-Guess-Xyz-77")
    await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    logged = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    for secret in ("Wrong-Guess-Xyz-77", ADMIN_PASSWORD, ADMIN_EMAIL):
        assert secret not in logged


async def test_unknown_login_fields_are_rejected(client: httpx.AsyncClient) -> None:
    res = await client.post(LOGIN, json={"email": "a@b.co", "password": "x", "is_admin": True})
    assert res.status_code == 422


# ---- session validation -----------------------------------------------------------------


@pytest.mark.parametrize("kind", ["garbage", "wrong_secret", "expired", "alg_none", "old_version"])
async def test_invalid_tokens_are_rejected(admin_user: AdminUser, kind: str) -> None:
    import jwt

    settings = get_settings()
    if kind == "garbage":
        token = "not-a-jwt"
    elif kind == "wrong_secret":
        other = settings.model_copy(update={"secret_key": SecretStr("x" * 90)})
        token = create_access_token(str(admin_user.id), 0, other)
    elif kind == "expired":
        token = create_access_token(
            str(admin_user.id), 0, settings, now=datetime.now(UTC) - timedelta(hours=9)
        )
    elif kind == "alg_none":
        now = int(datetime.now(UTC).timestamp())
        token = jwt.encode(
            {
                "sub": str(admin_user.id),
                "ver": 0,
                "typ": "admin_session",
                "iat": now,
                "exp": now + 600,
            },
            key=None,
            algorithm="none",
        )
    else:  # issued before a password change bumped the version
        token = create_access_token(str(admin_user.id), admin_user.token_version - 1, settings)
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


# ---- forced first-login password change -------------------------------------------------


async def test_seed_admin_must_change_password_before_using_the_admin(
    client: httpx.AsyncClient, seed_admin: AdminUser
) -> None:
    res = await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert res.status_code == 200 and res.json()["must_change_password"] is True
    assert (await client.get(ME)).json()["must_change_password"] is True

    blocked = await client.get("/api/v1/admin/today")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"

    changed = await client.post(
        CHANGE, json={"current_password": ADMIN_PASSWORD, "new_password": "Monsoon-Rooftop-48"}
    )
    assert changed.status_code == 204
    assert (await client.get(ME)).json()["must_change_password"] is False
    assert (await client.get("/api/v1/admin/today")).status_code == 200


# ---- change password --------------------------------------------------------------------


async def test_change_password_requires_current_password(admin_client: httpx.AsyncClient) -> None:
    res = await admin_client.post(
        CHANGE, json={"current_password": "wrong-one-here", "new_password": "Brand-New-Pass-42"}
    )
    assert res.status_code == 400
    assert "current_password" in res.json()["error"]["fields"]


@pytest.mark.parametrize(
    "weak",
    [
        "short",
        "x" * 80,  # over bcrypt's 72 bytes
        " leading-space-pass",
        "password1234",  # on the common list
        "MyPassword2026!",  # contains "password"
        "Envex-Solar-2026",  # contains the company name
        "123456789abc",  # contains a common sequence
        "abababababab",  # repeated pattern
        "owner-is-great-1",  # contains the email's local part ("owner@example.com")
    ],
)
async def test_change_password_rejects_weak_passwords(
    admin_client: httpx.AsyncClient, weak: str
) -> None:
    res = await admin_client.post(
        CHANGE, json={"current_password": ADMIN_PASSWORD, "new_password": weak}
    )
    assert res.status_code in (400, 422), res.text
    assert "new_password" in res.json()["error"]["fields"]


async def test_change_password_signs_out_every_other_session(
    admin_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    old_token = admin_client.cookies["envex_admin"]
    async with make_client("192.0.2.61") as other_device:
        other_device.cookies.set("envex_admin", old_token)
        assert (await other_device.get(ME)).status_code == 200

        res = await admin_client.post(
            CHANGE, json={"current_password": ADMIN_PASSWORD, "new_password": "Brand-New-Pass-42"}
        )
        assert res.status_code == 204
        assert (await admin_client.get(ME)).status_code == 200  # this device got a fresh cookie
        assert (await other_device.get(ME)).status_code == 401  # immediately, same second

    async with make_client("192.0.2.62") as c:
        assert (await _login(c, ADMIN_EMAIL, ADMIN_PASSWORD)).status_code == 401
        assert (await _login(c, ADMIN_EMAIL, "Brand-New-Pass-42")).status_code == 200
    assert "change_password" in (await session.execute(select(AuditLog.action))).scalars().all()


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
    with pytest.raises(ValueError, match="too common"):
        await create_or_reset_admin(
            session, email="new@example.com", full_name=None, password="iloveyou1234", reset=False
        )

    version_before = admin_user.token_version
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
    assert admin.must_change_password is True  # a reset password is a new seed
    assert admin.token_version == version_before + 1  # and signs out old sessions


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
        input="Monsoon-Cli-Seed-2026\n",
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Created admin cli@example.com (Cli User)." in result.stdout
    assert "Monsoon-Cli-Seed-2026" not in result.stdout + result.stderr
