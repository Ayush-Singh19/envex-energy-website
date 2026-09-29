"""Per-IP rate limiting (slowapi).

The client IP is ``request.client.host``. In production uvicorn runs with
``--proxy-headers`` so this is the visitor's IP, not the load balancer's.
Storage is in-memory by default, which is per-process: use Redis
(``RATE_LIMIT_STORAGE=redis://...``) once there is more than one worker.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.errors import error_body

limiter = Limiter(key_func=get_remote_address, storage_uri=get_settings().rate_limit_storage)


def enquiry_limit() -> str:
    return get_settings().rate_limit_enquiry


def events_limit() -> str:
    return get_settings().rate_limit_events


async def rate_limit_exceeded_handler(_: Request, __: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        error_body("rate_limited", "Too many requests. Please wait a few minutes and try again."),
        status_code=429,
    )
