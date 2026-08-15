from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from zylora_api.core.config import Settings

RETRYABLE_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


class AiBuilderError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class BuilderArtifact:
    object_key: str
    checksum_sha256: str
    size_bytes: int
    content_type: str


@dataclass(frozen=True, slots=True)
class BuilderExecutionResult:
    generation_id: UUID
    artifact: BuilderArtifact
    provider_name: str | None
    provider_model: str | None
    stage_durations_ms: dict[str, int]


class AiBuilderClient:
    """Stateless server-only boundary to the isolated generation orchestrator."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    def _credentials(self) -> str:
        if not self.settings.ai_builder_enabled:
            raise AiBuilderError("AI_BUILDER_DISABLED", retryable=False)
        token = self.settings.ai_builder_service_token
        if not token:
            raise AiBuilderError("AI_BUILDER_CONFIGURATION_INVALID", retryable=False)
        return token

    async def execute(
        self,
        *,
        generation_id: UUID,
        project_id: UUID,
        owner_user_id: UUID,
        prompt: str,
        lease_token: UUID,
    ) -> BuilderExecutionResult:
        token = self._credentials()
        owns_client = self.client is None
        timeout = httpx.Timeout(
            self.settings.ai_generation_timeout_seconds,
            connect=self.settings.ai_builder_connect_timeout_seconds,
        )
        client = self.client or httpx.AsyncClient(timeout=timeout)
        try:
            response = await client.post(
                f"{self.settings.ai_builder_url.rstrip('/')}/v1/generations/{generation_id}/execute",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": f"ai-generation:{generation_id}",
                    "Content-Type": "application/json",
                },
                json={
                    "generation_id": str(generation_id),
                    "project_id": str(project_id),
                    "owner_user_id": str(owner_user_id),
                    "lease_token": str(lease_token),
                    "prompt": prompt,
                },
            )
            payload = self._json_object(response)
            if response.status_code != 200:
                code = payload.get("error")
                safe_code = code if isinstance(code, str) else "INTERNAL_GENERATION_ERROR"
                declared_retryable = payload.get("retryable") is True
                raise AiBuilderError(
                    safe_code[:100],
                    retryable=declared_retryable or response.status_code in RETRYABLE_HTTP_STATUS,
                )
            return self._result(payload, generation_id)
        except AiBuilderError:
            raise
        except httpx.TimeoutException as error:
            raise AiBuilderError("AI_BUILDER_TIMEOUT", retryable=True) from error
        except httpx.HTTPError as error:
            raise AiBuilderError("AI_BUILDER_UNAVAILABLE", retryable=True) from error
        finally:
            if owns_client:
                await client.aclose()

    async def ready(self) -> bool:
        try:
            token = self._credentials()
        except AiBuilderError:
            return False
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(
            timeout=self.settings.ai_builder_connect_timeout_seconds
        )
        try:
            response = await client.get(
                f"{self.settings.ai_builder_url.rstrip('/')}/readiness",
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as error:
            raise AiBuilderError("INVALID_BUILDER_RESPONSE", retryable=False) from error
        if not isinstance(payload, dict):
            raise AiBuilderError("INVALID_BUILDER_RESPONSE", retryable=False)
        return payload

    @staticmethod
    def _result(payload: dict[str, Any], generation_id: UUID) -> BuilderExecutionResult:
        if payload.get("status") != "COMPLETED" or payload.get("generation_id") != str(
            generation_id
        ):
            raise AiBuilderError("INVALID_BUILDER_RESPONSE", retryable=False)
        artifact = payload.get("artifact")
        if not isinstance(artifact, dict):
            raise AiBuilderError("INVALID_BUILDER_RESPONSE", retryable=False)
        key = artifact.get("object_key")
        checksum = artifact.get("checksum_sha256")
        size = artifact.get("size_bytes")
        content_type = artifact.get("content_type")
        if (
            not isinstance(key, str)
            or not isinstance(checksum, str)
            or len(checksum) != 64
            or not isinstance(size, int)
            or size <= 0
            or not isinstance(content_type, str)
        ):
            raise AiBuilderError("INVALID_BUILDER_RESPONSE", retryable=False)
        durations = payload.get("stage_durations_ms")
        safe_durations = (
            {str(k)[:40]: int(v) for k, v in durations.items() if isinstance(v, int) and v >= 0}
            if isinstance(durations, dict)
            else {}
        )
        return BuilderExecutionResult(
            generation_id=generation_id,
            artifact=BuilderArtifact(key, checksum.lower(), size, content_type),
            provider_name=(
                str(payload["provider_name"])[:80] if payload.get("provider_name") else None
            ),
            provider_model=(
                str(payload["provider_model"])[:160] if payload.get("provider_model") else None
            ),
            stage_durations_ms=safe_durations,
        )
