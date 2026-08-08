from __future__ import annotations

import re
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"
_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def normalize_correlation_id(candidate: str | None) -> str:
    if candidate and _PATTERN.fullmatch(candidate):
        return candidate
    return uuid4().hex


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = normalize_correlation_id(request.headers.get(CORRELATION_HEADER))
        token = correlation_id_context.set(correlation_id)
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
            response.headers[CORRELATION_HEADER] = correlation_id
            return response
        finally:
            correlation_id_context.reset(token)
