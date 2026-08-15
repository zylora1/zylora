from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from zylora_api.core.config import Settings
from zylora_api.modules.ai_builder.client import AiBuilderError, BuilderArtifact
from zylora_api.storage.base import ObjectStorage
from zylora_api.storage.keys import validate_object_key


class GenerationArtifactVerifier:
    """Verifies sandbox-uploaded content before Core records an immutable version."""

    def __init__(self, storage: ObjectStorage, settings: Settings) -> None:
        self.storage = storage
        self.settings = settings

    def verify(
        self,
        artifact: BuilderArtifact,
        *,
        owner_user_id: UUID,
        project_id: UUID,
        generation_id: UUID,
    ) -> BuilderArtifact:
        try:
            key = validate_object_key(artifact.object_key)
        except ValueError as error:
            raise AiBuilderError("ARTIFACT_STORAGE_INVALID", retryable=False) from error
        prefix = f"ai-sites/{owner_user_id}/{project_id}/{generation_id}/"
        if not key.startswith(prefix):
            raise AiBuilderError("ARTIFACT_OWNERSHIP_INVALID", retryable=False)
        if artifact.content_type not in {
            "application/gzip",
            "application/x-tar",
            "application/zip",
        }:
            raise AiBuilderError("ARTIFACT_FORMAT_INVALID", retryable=False)
        if not 1 <= artifact.size_bytes <= self.settings.ai_max_artifact_bytes:
            raise AiBuilderError("ARTIFACT_SIZE_INVALID", retryable=False)
        try:
            payload = self.storage.get_bytes(key)
        except Exception as error:
            raise AiBuilderError("ARTIFACT_STORAGE_FAILED", retryable=True) from error
        if (
            len(payload) != artifact.size_bytes
            or len(payload) > self.settings.ai_max_artifact_bytes
        ):
            raise AiBuilderError("ARTIFACT_SIZE_INVALID", retryable=False)
        checksum = sha256(payload).hexdigest()
        if checksum != artifact.checksum_sha256:
            raise AiBuilderError("ARTIFACT_INTEGRITY_FAILED", retryable=False)
        expected_suffix = f"/{checksum}.tar.gz"
        if not key.endswith(expected_suffix):
            raise AiBuilderError("ARTIFACT_KEY_INVALID", retryable=False)
        return artifact
