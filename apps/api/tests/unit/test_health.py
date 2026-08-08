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
