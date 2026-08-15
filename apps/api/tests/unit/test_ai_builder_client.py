from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from zylora_api.core.config import Settings
from zylora_api.modules.ai_builder.client import AiBuilderClient, AiBuilderError


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "storage_provider": "memory",
        "ai_builder_enabled": True,
        "ai_builder_url": "https://builder.test",
        "ai_builder_service_token": "test-service-token-long-enough-for-tests",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def test_builder_execute_uses_server_auth_and_generation_idempotency() -> None:
    seen: dict[str, object] = {}
    generation_id = uuid4()
    project_id = uuid4()
    owner_id = uuid4()
    digest = "a" * 64
    object_key = f"ai-sites/{owner_id}/{project_id}/{generation_id}/{digest}.tar.gz"

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["Authorization"]
        seen["idempotency"] = request.headers["Idempotency-Key"]
        seen["body"] = request.content
        return httpx.Response(
            200,
            json={
                "generation_id": str(generation_id),
                "status": "COMPLETED",
                "artifact": {
                    "object_key": object_key,
                    "checksum_sha256": digest,
                    "size_bytes": 1024,
                    "content_type": "application/gzip",
                },
                "provider_name": "test-provider",
                "provider_model": "test-model",
                "stage_durations_ms": {"generating": 10},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AiBuilderClient(settings(), client).execute(
            generation_id=generation_id,
            project_id=project_id,
            owner_user_id=owner_id,
            prompt="Build a credible website for a local dental clinic.",
            lease_token=uuid4(),
        )
    assert result.generation_id == generation_id
    assert result.artifact.checksum_sha256 == digest
    assert seen["authorization"] == "Bearer test-service-token-long-enough-for-tests"
    assert seen["idempotency"] == f"ai-generation:{generation_id}"
    assert b"dental clinic" in seen["body"]


async def test_builder_classifies_retryable_and_terminal_failures() -> None:
    responses = iter(
        [
            httpx.Response(503, json={"error": "PROVIDER_UNAVAILABLE", "retryable": True}),
            httpx.Response(422, json={"error": "GENERATION_POLICY_REJECTED", "retryable": False}),
        ]
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: next(responses))
    ) as client:
        adapter = AiBuilderClient(settings(), client)
        for code, retryable in [
            ("PROVIDER_UNAVAILABLE", True),
            ("GENERATION_POLICY_REJECTED", False),
        ]:
            with pytest.raises(AiBuilderError) as captured:
                await adapter.execute(
                    generation_id=uuid4(),
                    project_id=uuid4(),
                    owner_user_id=uuid4(),
                    prompt="Build a professional website for a consultancy firm.",
                    lease_token=uuid4(),
                )
            assert captured.value.code == code
            assert captured.value.retryable is retryable


async def test_builder_fails_closed_when_disabled_unreachable_or_malformed() -> None:
    with pytest.raises(AiBuilderError, match="AI_BUILDER_DISABLED"):
        await AiBuilderClient(settings(ai_builder_enabled=False)).execute(
            generation_id=uuid4(),
            project_id=uuid4(),
            owner_user_id=uuid4(),
            prompt="Build a professional website for a consultancy firm.",
            lease_token=uuid4(),
        )

    def malformed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "COMPLETED", "artifact": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(malformed)) as client:
        with pytest.raises(AiBuilderError, match="INVALID_BUILDER_RESPONSE"):
            await AiBuilderClient(settings(), client).execute(
                generation_id=uuid4(),
                project_id=uuid4(),
                owner_user_id=uuid4(),
                prompt="Build a professional website for a consultancy firm.",
                lease_token=uuid4(),
            )


async def test_builder_readiness_is_server_authenticated() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["Authorization"]
        return httpx.Response(200, json={"status": "ready"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await AiBuilderClient(settings(), client).ready() is True
    assert seen["authorization"] == "Bearer test-service-token-long-enough-for-tests"


async def test_builder_client_classifies_transport_timeout_and_unavailability() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unavailable", request=request)

    for handler, code in [(timeout, "AI_BUILDER_TIMEOUT"), (unavailable, "AI_BUILDER_UNAVAILABLE")]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(AiBuilderError, match=code) as captured:
                await AiBuilderClient(settings(), client).execute(
                    generation_id=uuid4(),
                    project_id=uuid4(),
                    owner_user_id=uuid4(),
                    prompt="Build a professional website for a consultancy firm.",
                    lease_token=uuid4(),
                )
            assert captured.value.retryable is True


async def test_builder_client_rejects_missing_credentials_and_non_object_json() -> None:
    invalid = settings(ai_builder_enabled=False, ai_builder_service_token="")
    invalid.ai_builder_enabled = True
    with pytest.raises(AiBuilderError, match="AI_BUILDER_CONFIGURATION_INVALID"):
        await AiBuilderClient(invalid).execute(
            generation_id=uuid4(),
            project_id=uuid4(),
            owner_user_id=uuid4(),
            prompt="Build a professional website for a consultancy firm.",
            lease_token=uuid4(),
        )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=["not", "an", "object"]))
    ) as client:
        with pytest.raises(AiBuilderError, match="INVALID_BUILDER_RESPONSE"):
            await AiBuilderClient(settings(), client).execute(
                generation_id=uuid4(),
                project_id=uuid4(),
                owner_user_id=uuid4(),
                prompt="Build a professional website for a consultancy firm.",
                lease_token=uuid4(),
            )


async def test_builder_client_sanitizes_metadata_and_readiness_outages() -> None:
    generation_id = uuid4()
    payload = {
        "generation_id": str(generation_id),
        "status": "COMPLETED",
        "artifact": {
            "object_key": "safe/archive.tar.gz",
            "checksum_sha256": "A" * 64,
            "size_bytes": 1,
            "content_type": "application/gzip",
        },
        "provider_name": "p" * 100,
        "provider_model": "m" * 200,
        "stage_durations_ms": {"building": 12, "negative": -1, "bad": "value"},
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        result = await AiBuilderClient(settings(), client).execute(
            generation_id=generation_id,
            project_id=uuid4(),
            owner_user_id=uuid4(),
            prompt="Build a professional website for a consultancy firm.",
            lease_token=uuid4(),
        )
    assert result.artifact.checksum_sha256 == "a" * 64
    assert len(result.provider_name or "") == 80
    assert len(result.provider_model or "") == 160
    assert result.stage_durations_ms == {"building": 12}

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(offline)) as client:
        assert await AiBuilderClient(settings(), client).ready() is False
    assert await AiBuilderClient(settings(ai_builder_enabled=False)).ready() is False
