"""Per-IP rate limiting (slowapi).

Keyed on the visitor's IP as resolved by ``app.core.client_ip`` (which only trusts
X-Forwarded-For entries added by our own proxies, so it can't be spoofed).
Storage is in-memory by default, which is per-process: use Redis
(``RATE_LIMIT_STORAGE=redis://...``) once there is more than one worker.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.client_ip import rate_limit_key
from app.core.config import get_settings
from app.core.errors import error_body

limiter = Limiter(key_func=rate_limit_key, storage_uri=get_settings().rate_limit_storage)


def enquiry_limit() -> str:
    return get_settings().rate_limit_enquiry


def events_limit() -> str:
    return get_settings().rate_limit_events


def login_limit() -> str:
    return get_settings().rate_limit_login


async def rate_limit_exceeded_handler(_: Request, __: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        error_body("rate_limited", "Too many requests. Please wait a few minutes and try again."),
        status_code=429,
    )
