"""The visitor's IP address, used for rate limits and stored with enquiries/audit entries.

``X-Forwarded-For`` is a list the client can pre-fill with anything, so only the entries
appended by *our own* proxies can be trusted. With ``TRUSTED_PROXY_HOPS=1`` (Render,
Railway and most PaaS load balancers) the last entry is the real visitor. With 0 (local,
or the app exposed directly) the header is ignored and the socket peer is used.
Values that aren't valid IP addresses are discarded rather than stored.
"""

import ipaddress

from starlette.requests import Request

from app.core.config import get_settings


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def client_ip(request: Request) -> str | None:
    peer = request.client.host if request.client else None
    hops = get_settings().trusted_proxy_hops
    if hops > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        entries = [e.strip() for e in forwarded.split(",") if e.strip()]
        if len(entries) >= hops and (ip := _valid_ip(entries[-hops])):
            return ip
    return _valid_ip(peer)


def rate_limit_key(request: Request) -> str:
    return client_ip(request) or "unknown"
