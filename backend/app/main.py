"""App factory: settings, logging, middleware, error handlers and routers."""

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.api.v1 import admin, auth, public
from app.core.config import Settings, get_settings
from app.core.constants import MAX_REQUEST_BYTES
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

API_PREFIX = "/api/v1"
ADMIN_UI_DIR = Path(__file__).resolve().parent / "admin_ui"

logger = logging.getLogger(__name__)


def _scrub_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """On top of send_default_pii=False: drop anything request- or user-shaped."""
    request = event.get("request")
    if isinstance(request, dict):
        for key in ("data", "cookies", "query_string", "env"):
            request.pop(key, None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                k: v for k, v in headers.items() if k.lower() in {"user-agent", "x-request-id"}
            }
    event.pop("user", None)
    return event


def _init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        send_default_pii=False,  # no IPs, cookies or user data in error reports
        max_request_body_size="never",  # never attach request bodies (enquiry text)
        before_send=_scrub_event,
        traces_sample_rate=0.0,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()
    _init_sentry(settings)

    # Interactive docs are handy locally but only widen the attack surface in production.
    docs = not settings.is_production
    app = FastAPI(
        title=f"{settings.company_name} API",
        version="1.0.0",
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )

    register_exception_handlers(app)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Starlette runs the last-added middleware first, so RequestContext wraps everything.
    # The size limit sits inside CORS, so a 413 still carries CORS headers for the browser.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # the public site never sends cookies; /admin is same-origin
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(public.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(admin.router, prefix=API_PREFIX)

    # Admin dashboard: static HTML/CSS/JS, same origin as the API (so the cookie just works).
    @app.get("/", include_in_schema=False)
    async def _root() -> RedirectResponse:
        return RedirectResponse("/admin/")

    app.mount("/admin", StaticFiles(directory=ADMIN_UI_DIR, html=True), name="admin")

    logger.info("app_started", extra={"env": settings.app_env})
    return app


app = create_app()
