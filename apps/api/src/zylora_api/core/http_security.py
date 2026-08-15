from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class ApiSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply safe browser defaults to direct API responses as well as proxied ones."""

    def __init__(self, app: ASGIApp, *, production: bool) -> None:
        super().__init__(app)
        self._production = production

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"
        )

        if request.url.path.startswith("/api/v1/"):
            headers.setdefault("Cache-Control", "private, no-store")
            headers.setdefault("X-Robots-Tag", "noindex, nofollow")
            headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )

        if self._production:
            headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response
