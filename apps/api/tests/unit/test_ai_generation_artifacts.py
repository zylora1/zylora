from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

import pytest
from zylora_api.core.config import Settings
from zylora_api.modules.ai_builder.artifacts import GenerationArtifactVerifier
from zylora_api.modules.ai_builder.client import AiBuilderError, BuilderArtifact
from zylora_api.storage.memory import MemoryObjectStorage


def verifier() -> tuple[GenerationArtifactVerifier, MemoryObjectStorage]:
    storage = MemoryObjectStorage()
    settings = Settings(_env_file=None, environment="test", storage_provider="memory")
    return GenerationArtifactVerifier(storage, settings), storage


def test_generation_artifact_verifies_owner_path_size_and_checksum() -> None:
    check, storage = verifier()
    owner, project, generation = uuid4(), uuid4(), uuid4()
    payload = b"immutable generated website archive"
    digest = sha256(payload).hexdigest()
    key = f"ai-sites/{owner}/{project}/{generation}/{digest}.tar.gz"
    storage.put_bytes(key, payload, "application/gzip")
    artifact = BuilderArtifact(key, digest, len(payload), "application/gzip")
    assert (
        check.verify(artifact, owner_user_id=owner, project_id=project, generation_id=generation)
        == artifact
    )


def test_generation_artifact_rejects_cross_owner_and_integrity_forgery() -> None:
    check, storage = verifier()
    owner, project, generation = uuid4(), uuid4(), uuid4()
    payload = b"artifact"
    digest = sha256(payload).hexdigest()
    forged_key = f"ai-sites/{uuid4()}/{project}/{generation}/{digest}.tar.gz"
    storage.put_bytes(forged_key, payload, "application/gzip")
    with pytest.raises(AiBuilderError, match="ARTIFACT_OWNERSHIP_INVALID"):
        check.verify(
            BuilderArtifact(forged_key, digest, len(payload), "application/gzip"),
            owner_user_id=owner,
            project_id=project,
            generation_id=generation,
        )

    key = f"ai-sites/{owner}/{project}/{generation}/{digest}.tar.gz"
    storage.put_bytes(key, payload, "application/gzip")
    with pytest.raises(AiBuilderError, match="ARTIFACT_INTEGRITY_FAILED"):
        check.verify(
            BuilderArtifact(key, "0" * 64, len(payload), "application/gzip"),
            owner_user_id=owner,
            project_id=project,
            generation_id=generation,
        )


def test_generation_artifact_rejects_invalid_key_format_size_and_suffix() -> None:
    check, storage = verifier()
    owner, project, generation = uuid4(), uuid4(), uuid4()
    payload = b"artifact"
    digest = sha256(payload).hexdigest()
    valid_key = f"ai-sites/{owner}/{project}/{generation}/{digest}.tar.gz"
    storage.put_bytes(valid_key, payload, "application/gzip")

    cases = [
        BuilderArtifact("../artifact.tar.gz", digest, len(payload), "application/gzip"),
        BuilderArtifact(valid_key, digest, len(payload), "application/octet-stream"),
        BuilderArtifact(valid_key, digest, 0, "application/gzip"),
        BuilderArtifact(valid_key, digest, len(payload) + 1, "application/gzip"),
        BuilderArtifact(
            f"ai-sites/{owner}/{project}/{generation}/wrong.tar.gz",
            digest,
            len(payload),
            "application/gzip",
        ),
    ]
    for artifact in cases:
        with pytest.raises(AiBuilderError):
            check.verify(
                artifact,
                owner_user_id=owner,
                project_id=project,
                generation_id=generation,
            )


def test_generation_artifact_classifies_storage_outage_as_retryable() -> None:
    class FailedStorage:
        def get_bytes(self, _key: str) -> bytes:
            raise ConnectionError("private storage outage")

    owner, project, generation = uuid4(), uuid4(), uuid4()
    digest = "a" * 64
    key = f"ai-sites/{owner}/{project}/{generation}/{digest}.tar.gz"
    check = GenerationArtifactVerifier(
        FailedStorage(),  # type: ignore[arg-type]
        Settings(_env_file=None, environment="test", storage_provider="memory"),
    )
    with pytest.raises(AiBuilderError, match="ARTIFACT_STORAGE_FAILED") as captured:
        check.verify(
            BuilderArtifact(key, digest, 1, "application/gzip"),
            owner_user_id=owner,
            project_id=project,
            generation_id=generation,
        )
    assert captured.value.retryable is True
