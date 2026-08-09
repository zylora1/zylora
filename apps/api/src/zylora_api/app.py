from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from zylora_api import __version__
from zylora_api.api.router import api_router
from zylora_api.core.config import get_settings
from zylora_api.core.correlation import CorrelationIdMiddleware
from zylora_api.core.logging import configure_logging
from zylora_api.core.problems import auth_problem_handler, validation_problem_handler
from zylora_api.modules.auth.errors import AuthProblem


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings().log_level)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Zylora V2 API",
        version=__version__,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_exception_handler(AuthProblem, auth_problem_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_problem_handler)  # type: ignore[arg-type]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[*settings.allowed_origins, settings.admin_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Correlation-ID", "Idempotency-Key"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(api_router)
    return app


app = create_app()
