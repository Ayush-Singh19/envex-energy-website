"""Admin sign-in. The session is a JWT in an httpOnly, SameSite=Strict cookie."""

from fastapi import APIRouter, Request, Response

from app.api.deps import ClientIpDep, SessionAdmin, SessionDep, SettingsDep
from app.core.config import Settings
from app.core.constants import AUTH_COOKIE_NAME
from app.core.rate_limit import limiter, login_limit
from app.models import AdminUser
from app.schemas.auth import ChangePasswordIn, LoginIn, MeOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _me(admin: AdminUser, settings: Settings) -> MeOut:
    return MeOut(
        id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
        company_name=settings.company_name,
        must_change_password=admin.must_change_password,
    )


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,  # not readable from JavaScript
        secure=settings.is_production,  # HTTPS only in production
        samesite="strict",  # never sent on cross-site requests (CSRF protection)
        path="/",
    )


@router.post("/login", response_model=MeOut)
@limiter.limit(login_limit)
async def login(
    request: Request,  # required by the rate limiter
    payload: LoginIn,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    ip: ClientIpDep,
) -> MeOut:
    admin, token = await auth_service.login(session, payload, ip, settings)
    _set_session_cookie(response, token, settings)
    return _me(admin, settings)


@router.post("/logout", status_code=204, response_class=Response)
async def logout(
    request: Request, session: SessionDep, settings: SettingsDep, ip: ClientIpDep
) -> Response:
    # Works even with an expired session, so the button always signs you out.
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token and (admin := await auth_service.authenticate(session, token, settings)):
        await auth_service.record_logout(session, admin, ip)
    response = Response(status_code=204)
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", samesite="strict", httponly=True)
    return response


@router.get("/me", response_model=MeOut)
async def me(admin: SessionAdmin, settings: SettingsDep) -> MeOut:
    return _me(admin, settings)


@router.post("/change-password", status_code=204, response_class=Response)
async def change_password(
    payload: ChangePasswordIn,
    admin: SessionAdmin,  # allowed while a password change is required
    session: SessionDep,
    settings: SettingsDep,
    ip: ClientIpDep,
) -> Response:
    token = await auth_service.change_password(session, admin, payload, ip, settings)
    response = Response(status_code=204)
    _set_session_cookie(response, token, settings)  # keep this device signed in
    return response
