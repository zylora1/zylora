from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from zylora_api.modules.auth.errors import AuthProblem


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "unavailable"))


async def auth_problem_handler(request: Request, error: AuthProblem) -> JSONResponse:
    headers = (
        {"Retry-After": str(error.retry_after_seconds or 900)}
        if error.code == "rate_limited"
        else None
    )
    return JSONResponse(
        status_code=error.status_code,
        headers=headers,
        media_type="application/problem+json",
        content={
            "type": f"https://api.zylora.com/problems/{error.code}",
            "title": error.title,
            "status": error.status_code,
            "detail": error.detail,
            "code": error.code,
            "correlation_id": _correlation_id(request),
            **(
                {"retry_after_seconds": error.retry_after_seconds}
                if error.retry_after_seconds is not None
                else {}
            ),
        },
    )


async def validation_problem_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    fields = [
        {
            "field": ".".join(str(part) for part in issue["loc"] if part != "body"),
            "code": str(issue["type"]),
        }
        for issue in error.errors()
    ]
    return JSONResponse(
        status_code=422,
        media_type="application/problem+json",
        content={
            "type": "https://api.zylora.com/problems/validation_failed",
            "title": "Request validation failed",
            "status": 422,
            "detail": "One or more request fields are invalid.",
            "code": "validation_failed",
            "correlation_id": _correlation_id(request),
            "errors": fields,
        },
    )
