"""App factory: settings, logging, middleware, error handlers and routers."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import public
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

API_PREFIX = "/api/v1"

logger = logging.getLogger(__name__)


def _init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        send_default_pii=False,  # no IPs, cookies or bodies in error reports
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

    # Starlette runs the last-added middleware first, so RequestContext wraps everything.
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

    logger.info("app_started", extra={"env": settings.app_env})
    return app


app = create_app()
