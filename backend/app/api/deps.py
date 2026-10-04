"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client_ip import client_ip
from app.core.config import Settings, get_settings
from app.core.constants import AUTH_COOKIE_NAME
from app.core.errors import AppError, UnauthorizedError
from app.db.session import get_session
from app.models import AdminUser
from app.services import auth_service
from app.services.enquiry_service import RequestMeta

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_request_meta(request: Request) -> RequestMeta:
    return RequestMeta(ip_address=client_ip(request), user_agent=request.headers.get("user-agent"))


RequestMetaDep = Annotated[RequestMeta, Depends(get_request_meta)]
ClientIpDep = Annotated[str | None, Depends(client_ip)]


async def get_session_admin(
    request: Request, session: SessionDep, settings: SettingsDep
) -> AdminUser:
    """Any signed-in admin, including one who still has to replace the seed password."""
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise UnauthorizedError("Please sign in.")
    admin = await auth_service.authenticate(session, token, settings)
    if admin is None:
        raise UnauthorizedError("Your session has ended. Please sign in again.")
    return admin


async def get_current_admin(
    admin: Annotated[AdminUser, Depends(get_session_admin)],
) -> AdminUser:
    """Guards every /admin route: signed in, active, and past the forced password change."""
    if admin.must_change_password:
        raise AppError(
            403,
            "password_change_required",
            "Please choose a new password before using the admin page.",
        )
    return admin


SessionAdmin = Annotated[AdminUser, Depends(get_session_admin)]
CurrentAdmin = Annotated[AdminUser, Depends(get_current_admin)]
