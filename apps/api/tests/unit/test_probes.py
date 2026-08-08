from __future__ import annotations

from typing import Any, cast

import pytest
from redis.asyncio import Redis
from zylora_api.api.health import DatabaseProbe, RedisProbe


class ConnectionContext:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def __aenter__(self) -> ConnectionContext:
        if self.fail:
            raise OSError("database unavailable")
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, _: object) -> None:
        return None


class FakeEngine:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def connect(self) -> ConnectionContext:
        return ConnectionContext(fail=self.fail)


class FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.closed = False

    async def ping(self) -> bool:
        if self.fail:
            raise OSError("redis unavailable")
        return True

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.parametrize("fail", [False, True])
async def test_database_probe_contains_failures(fail: bool) -> None:
    probe = DatabaseProbe(cast(Any, FakeEngine(fail=fail)))
    assert await probe.check() is (not fail)


@pytest.mark.parametrize("fail", [False, True])
async def test_redis_probe_contains_failures(monkeypatch: pytest.MonkeyPatch, fail: bool) -> None:
    client = FakeRedis(fail=fail)
    monkeypatch.setattr(Redis, "from_url", lambda *_args, **_kwargs: client)
    assert await RedisProbe("redis://example").check() is (not fail)
    assert client.closed is True
