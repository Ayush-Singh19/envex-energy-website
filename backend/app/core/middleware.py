"""Request-ID, request logging, request size limit and security headers.

Written as pure ASGI middleware so it doesn't interfere with background tasks or
streaming responses (the CSV export streams).
"""

import ipaddress
import json
import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.client_ip import client_ip
from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9\-_.]{1,64}$")

# The admin UI runs only its own script, and loads Manrope from Google Fonts. Nothing else.
ADMIN_CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)


def truncate_ip(ip: str | None) -> str | None:
    """203.0.113.57 -> 203.0.113.0; IPv6 keeps the /48 prefix. Enough to spot abuse
    patterns, not enough to identify a person."""
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{addr}/{prefix}", strict=False).network_address)


class RequestContextMiddleware:
    """Assigns an X-Request-ID (or accepts a sane incoming one) and logs one line per request.

    Only method, path, status, timing and a truncated client IP are logged: no query
    strings, bodies or headers, so personal data never reaches the logs.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    "client": truncate_ip(client_ip(Request(scope))),
                },
            )
            request_id_var.reset(token)


class BodySizeLimitMiddleware:
    """Rejects request bodies over max_bytes with 413, before any route parses them.

    Checks the declared Content-Length up front, and counts streamed (chunked) bodies as
    they arrive, so a missing or false header doesn't get around the limit.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def _reject(self, send: Send) -> None:
        body = json.dumps(
            {"error": {"code": "payload_too_large", "message": "The request is too large."}}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > self.max_bytes
            except ValueError:
                too_big = True
            if too_big:
                await self._reject(send)
                return

        received = 0
        started = False
        rejected = False

        # Raising from receive() doesn't work: FastAPI turns any error while reading the body
        # into a 400. Instead, answer 413 ourselves, tell the app the client went away, and
        # drop whatever the app then tries to send.
        async def limited_receive() -> Message:
            nonlocal received, rejected, started
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    rejected = True
                    if not started:
                        started = True
                        await self._reject(send)
                    return {"type": "http.disconnect"}
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if rejected:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        await self.app(scope, limited_receive, tracking_send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Frame-Options"] = "DENY"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if self.hsts:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                if path == "/admin" or path.startswith("/admin/"):
                    headers["Content-Security-Policy"] = ADMIN_CSP
                if path.startswith("/api/v1/admin") or path.startswith("/api/v1/auth"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_wrapper)
