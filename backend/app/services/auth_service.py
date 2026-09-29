"""Admin authentication: login with lockout, session validation, password changes."""

import logging
import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.constants import LOCKOUT_MINUTES, MAX_FAILED_LOGINS, AuditAction
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    dummy_hash,
    hash_password,
    verify_password,
)
from app.models import AdminUser
from app.repositories.admin_repo import AdminRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.auth import ChangePasswordIn, LoginIn, check_password_strength

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Email or password is incorrect."


def _locked_error(until: datetime, now: datetime) -> AppError:
    minutes = max(1, math.ceil((until - now).total_seconds() / 60))
    unit = "minute" if minutes == 1 else "minutes"
    return AppError(
        423,
        "account_locked",
        f"Too many wrong passwords. Try again in {minutes} {unit}.",
    )


async def login(
    session: AsyncSession, data: LoginIn, ip: str | None, settings: Settings
) -> tuple[AdminUser, str]:
    repo = AdminRepository(session)
    admin = await repo.get_by_email(data.email)
    now = datetime.now(UTC)

    if admin is None or not admin.is_active:
        # Same bcrypt cost as a real check, so timing doesn't reveal which emails exist.
        await run_in_threadpool(verify_password, data.password, dummy_hash())
        logger.info("login_failed", extra={"reason": "unknown_or_inactive"})
        raise AppError(401, "invalid_credentials", INVALID_CREDENTIALS)

    if admin.locked_until and admin.locked_until > now:
        logger.info("login_blocked_locked", extra={"admin_id": str(admin.id)})
        raise _locked_error(admin.locked_until, now)

    if not await run_in_threadpool(verify_password, data.password, admin.password_hash):
        admin.failed_attempts += 1
        if admin.failed_attempts >= MAX_FAILED_LOGINS:
            admin.failed_attempts = 0
            admin.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            await session.commit()
            logger.warning("login_locked", extra={"admin_id": str(admin.id)})
            raise _locked_error(admin.locked_until, now)
        await session.commit()
        logger.info("login_failed", extra={"reason": "bad_password", "admin_id": str(admin.id)})
        raise AppError(401, "invalid_credentials", INVALID_CREDENTIALS)

    admin.failed_attempts = 0
    admin.locked_until = None
    admin.last_login_at = now
    await AuditRepository(session).add(
        admin_id=admin.id,
        action=AuditAction.LOGIN,
        entity_type="admin_user",
        entity_id=admin.id,
        ip_address=ip,
    )
    await session.commit()
    logger.info("login_succeeded", extra={"admin_id": str(admin.id)})
    return admin, create_access_token(str(admin.id), settings, now)


async def authenticate(session: AsyncSession, token: str, settings: Settings) -> AdminUser | None:
    """The admin a session token belongs to, or None if the token is no longer valid."""
    claims = decode_access_token(token, settings)
    if claims is None:
        return None
    try:
        admin_id = uuid.UUID(str(claims["sub"]))
    except ValueError:
        return None
    admin = await AdminRepository(session).get(admin_id)
    if admin is None or not admin.is_active:
        return None
    # A password change signs out every session issued before it.
    if admin.password_changed_at and int(claims["iat"]) < int(
        admin.password_changed_at.timestamp()
    ):
        return None
    return admin


async def record_logout(session: AsyncSession, admin: AdminUser, ip: str | None) -> None:
    await AuditRepository(session).add(
        admin_id=admin.id,
        action=AuditAction.LOGOUT,
        entity_type="admin_user",
        entity_id=admin.id,
        ip_address=ip,
    )
    await session.commit()


async def change_password(
    session: AsyncSession,
    admin: AdminUser,
    data: ChangePasswordIn,
    ip: str | None,
    settings: Settings,
) -> str:
    """Returns a fresh session token; every other session for this admin stops working."""
    if not await run_in_threadpool(verify_password, data.current_password, admin.password_hash):
        raise AppError(
            400,
            "invalid_password",
            "Your current password is incorrect.",
            fields={"current_password": "Your current password is incorrect."},
        )
    if data.new_password == data.current_password:
        raise AppError(
            400,
            "password_unchanged",
            "Choose a password you haven't used here before.",
            fields={"new_password": "The new password must be different."},
        )

    now = datetime.now(UTC).replace(microsecond=0)
    admin.password_hash = await run_in_threadpool(hash_password, data.new_password)
    admin.password_changed_at = now
    await AuditRepository(session).add(
        admin_id=admin.id,
        action=AuditAction.CHANGE_PASSWORD,
        entity_type="admin_user",
        entity_id=admin.id,
        ip_address=ip,
    )
    await session.commit()
    logger.info("password_changed", extra={"admin_id": str(admin.id)})
    return create_access_token(str(admin.id), settings, now)


async def create_or_reset_admin(
    session: AsyncSession, *, email: str, full_name: str | None, password: str, reset: bool
) -> tuple[AdminUser, bool]:
    """Used by the CLI script. Returns (admin, created)."""
    check_password_strength(password)
    email = email.strip().lower()
    repo = AdminRepository(session)
    existing = await repo.get_by_email(email)
    password_hash = await run_in_threadpool(hash_password, password)
    now = datetime.now(UTC).replace(microsecond=0)

    if existing is not None:
        if not reset:
            raise ValueError(f"An admin with email {email} already exists. Use --reset.")
        existing.password_hash = password_hash
        existing.password_changed_at = now
        existing.failed_attempts = 0
        existing.locked_until = None
        existing.is_active = True
        if full_name:
            existing.full_name = full_name
        await session.commit()
        return existing, False

    admin = await repo.add(
        AdminUser(
            email=email,
            full_name=full_name or email.split("@")[0],
            password_hash=password_hash,
            password_changed_at=now,
        )
    )
    await session.commit()
    return admin, True
