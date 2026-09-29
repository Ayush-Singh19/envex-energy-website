"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.services.enquiry_service import RequestMeta

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_request_meta(request: Request) -> RequestMeta:
    return RequestMeta(ip_address=client_ip(request), user_agent=request.headers.get("user-agent"))


RequestMetaDep = Annotated[RequestMeta, Depends(get_request_meta)]
