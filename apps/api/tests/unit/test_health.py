from dataclasses import dataclass

import httpx
import pytest
from zylora_api.api.health import ReadinessService, get_readiness_service
from zylora_api.app import create_app


@dataclass
class StaticProbe:
    result: bool

    async def check(self) -> bool:
        return self.result


@pytest.mark.parametrize(
    ("database", "redis", "expected_status", "expected_code"),
    [
        (True, True, "ready", 200),
        (True, False, "degraded", 200),
        (False, True, "not_ready", 503),
    ],
)
async def test_readiness_reflects_required_and_degraded_dependencies(
    database: bool, redis: bool, expected_status: str, expected_code: int
) -> None:
    app = create_app()
    app.dependency_overrides[get_readiness_service] = lambda: ReadinessService(
        StaticProbe(database), StaticProbe(redis)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/readiness", headers={"X-Correlation-ID": "request-12345678"})

    assert response.status_code == expected_code
    assert response.json()["status"] == expected_status
    assert response.headers["X-Correlation-ID"] == "request-12345678"


async def test_liveness_has_no_dependency_probe() -> None:
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/liveness")

    assert response.status_code == 200
    assert response.json() == {
        "service": "zylora-api",
        "status": "alive",
        "version": "0.1.0",
        "checks": None,
    }


@pytest.mark.parametrize(
    ("identity", "builder", "storage", "expected_check"),
    [
        (False, True, True, "identity"),
        (True, False, True, "ai_builder"),
        (True, True, False, "ai_artifact_storage"),
    ],
)
async def test_optional_production_ai_dependencies_fail_readiness_closed(
    identity: bool, builder: bool, storage: bool, expected_check: str
) -> None:
    service = ReadinessService(
        StaticProbe(True),
        StaticProbe(True),
        identity=StaticProbe(identity),
        ai_builder=StaticProbe(builder),
        artifact_storage=StaticProbe(storage),
    )
    status, checks = await service.evaluate()
    assert status == "not_ready"
    assert checks[expected_check] == "not_ready"


async def test_all_required_ai_dependencies_can_be_ready() -> None:
    service = ReadinessService(
        StaticProbe(True),
        StaticProbe(True),
        identity=StaticProbe(True),
        ai_builder=StaticProbe(True),
        artifact_storage=StaticProbe(True),
    )
    assert await service.evaluate() == (
        "ready",
        {
            "database": "ready",
            "redis": "ready",
            "identity": "ready",
            "ai_builder": "ready",
            "ai_artifact_storage": "ready",
        },
    )
