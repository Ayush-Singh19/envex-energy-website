"""Per-IP rate limiting (slowapi).

Keyed on the visitor's IP as resolved by ``app.core.client_ip`` (which only trusts
X-Forwarded-For entries added by our own proxies, so it can't be spoofed).
Storage is in-memory by default, which is per-process: use Redis
(``RATE_LIMIT_STORAGE=redis://...``) once there is more than one worker.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.client_ip import rate_limit_key
from app.core.config import get_settings
from app.core.errors import error_body

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=rate_limit_key, storage_uri=get_settings().rate_limit_storage)


def enquiry_limit() -> str:
    return get_settings().rate_limit_enquiry


def events_limit() -> str:
    return get_settings().rate_limit_events


def login_limit() -> str:
    return get_settings().rate_limit_login


async def rate_limit_exceeded_handler(request: Request, _: RateLimitExceeded) -> JSONResponse:
    # Rate-limit hits are logged (path + truncated IP) so abuse is visible; no personal data.
    from app.core.middleware import truncate_ip

    logger.warning(
        "rate_limited",
        extra={"path": request.url.path, "client": truncate_ip(rate_limit_key(request))},
    )
    message = "Too many requests. Please wait a few minutes and try again."
    if request.url.path.endswith("/enquiries"):
        # The security doc asks for the phone number here, so a real customer still gets through.
        message = (
            "We've received several enquiries from this connection. Please call us on "
            f"{get_settings().call_number_display} or try again in a few minutes."
        )
    return JSONResponse(error_body("rate_limited", message), status_code=429)
