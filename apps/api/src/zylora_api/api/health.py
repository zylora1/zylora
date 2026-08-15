from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from zylora_api import __version__
from zylora_api.core.config import Settings, get_settings
from zylora_api.db.session import get_engine

router = APIRouter(tags=["operations"])


class Probe(Protocol):
    async def check(self) -> bool: ...


class DatabaseProbe:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


class AiBuilderReadinessProbe:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check(self) -> bool:
        from zylora_api.modules.ai_builder.client import AiBuilderClient

        return await AiBuilderClient(self._settings).ready()


class ArtifactStorageReadinessProbe:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check(self) -> bool:
        from zylora_api.modules.publishing.runtime import publication_storage_for

        storage = publication_storage_for(self._settings)
        return await asyncio.to_thread(storage.check)


class IdentityReadinessProbe:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> bool:
        statement = text(
            "SELECT count(*) = 1 FROM users u "
            "JOIN super_admin_profiles p ON p.user_id = u.id "
            "WHERE u.account_type = 'SUPER_ADMIN' AND u.status = 'ACTIVE'"
        )
        try:
            async with self._engine.connect() as connection:
                return bool(await connection.scalar(statement))
        except Exception:
            return False


class RedisProbe:
    def __init__(self, url: str) -> None:
        self._url = url

    async def check(self) -> bool:
        client = Redis.from_url(self._url, socket_connect_timeout=1, socket_timeout=1)
        try:
            return bool(await client.ping())
        except Exception:
            return False
        finally:
            await client.aclose()


@dataclass(frozen=True, slots=True)
class ReadinessService:
    database: Probe
    redis: Probe
    identity: Probe | None = None
    ai_builder: Probe | None = None
    artifact_storage: Probe | None = None

    async def evaluate(self) -> tuple[str, dict[str, str]]:
        database_ready = await self.database.check()
        redis_ready = await self.redis.check()
        checks = {
            "database": "ready" if database_ready else "not_ready",
            "redis": "ready" if redis_ready else "degraded",
        }
        if self.identity is not None:
            identity_ready = await self.identity.check()
            checks["identity"] = "ready" if identity_ready else "not_ready"
            if not identity_ready:
                return "not_ready", checks
        if self.ai_builder is not None:
            builder_ready = await self.ai_builder.check()
            checks["ai_builder"] = "ready" if builder_ready else "not_ready"
            if not builder_ready:
                return "not_ready", checks
        if self.artifact_storage is not None:
            storage_ready = await self.artifact_storage.check()
            checks["ai_artifact_storage"] = "ready" if storage_ready else "not_ready"
            if not storage_ready:
                return "not_ready", checks
        if not database_ready:
            return "not_ready", checks
        if not redis_ready:
            return "degraded", checks
        return "ready", checks


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    status: str
    version: str
    checks: dict[str, str] | None = None


def get_readiness_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadinessService:
    identity = (
        IdentityReadinessProbe(get_engine()) if settings.environment == "production" else None
    )
    ai_builder = AiBuilderReadinessProbe(settings) if settings.ai_builder_enabled else None
    artifact_storage = (
        ArtifactStorageReadinessProbe(settings) if settings.ai_builder_enabled else None
    )
    return ReadinessService(
        DatabaseProbe(get_engine()),
        RedisProbe(settings.redis_url),
        identity,
        ai_builder,
        artifact_storage,
    )


@router.get("/liveness", response_model=HealthResponse, operation_id="getLiveness")
async def liveness() -> HealthResponse:
    return HealthResponse(service="zylora-api", status="alive", version=__version__)


@router.get("/readiness", response_model=HealthResponse, operation_id="getReadiness")
async def readiness(
    response: Response,
    service: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> HealthResponse:
    readiness_status, checks = await service.evaluate()
    if readiness_status == "not_ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        service="zylora-api",
        status=readiness_status,
        version=__version__,
        checks=checks,
    )


@router.get("/version", response_model=HealthResponse, operation_id="getVersion")
async def version() -> HealthResponse:
    return HealthResponse(service="zylora-api", status="available", version=__version__)
