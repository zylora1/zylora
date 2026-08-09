from __future__ import annotations

from dataclasses import dataclass

from zylora_api.api.health import ReadinessService


@dataclass
class StaticProbe:
    result: bool

    async def check(self) -> bool:
        return self.result


async def test_identity_readiness_is_required_when_configured() -> None:
    service = ReadinessService(StaticProbe(True), StaticProbe(True), StaticProbe(False))

    readiness_status, checks = await service.evaluate()

    assert readiness_status == "not_ready"
    assert checks["identity"] == "not_ready"
