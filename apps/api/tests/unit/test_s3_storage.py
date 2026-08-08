from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from zylora_api.core.config import Settings
from zylora_api.storage.s3 import S3ObjectStorage


class FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.payload = b"stored"

    def put_object(self, **kwargs: Any) -> None:
        self.calls.append(("put", kwargs))

    def get_object(self, **kwargs: Any) -> dict[str, BytesIO]:
        self.calls.append(("get", kwargs))
        return {"Body": BytesIO(self.payload)}

    def delete_object(self, **kwargs: Any) -> None:
        self.calls.append(("delete", kwargs))

    def generate_presigned_url(self, operation: str, **kwargs: Any) -> str:
        self.calls.append((operation, kwargs))
        return "https://objects.example/signed"


def s3_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        storage_provider="s3",
        s3_endpoint_url="https://objects.example",
        s3_bucket="zylora-test",
        s3_access_key="test-access",
        s3_secret_key="test-secret",
    )


def test_s3_adapter_uses_private_encrypted_object_operations() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(s3_settings(), client=client)

    metadata = storage.put_bytes("private/object.txt", b"stored", "text/plain")
    assert metadata.size == 6
    assert client.calls[0][1]["ServerSideEncryption"] == "AES256"
    assert storage.get_bytes(metadata.key) == b"stored"
    assert storage.presign_get(metadata.key, 60) == "https://objects.example/signed"
    storage.delete(metadata.key)
    assert [call[0] for call in client.calls] == ["put", "get", "get_object", "delete"]


def test_s3_adapter_requires_s3_configuration_and_bounded_expiry() -> None:
    with pytest.raises(ValueError, match="requires storage_provider=s3"):
        S3ObjectStorage(Settings(_env_file=None, environment="test", storage_provider="memory"))

    storage = S3ObjectStorage(s3_settings(), client=FakeS3Client())
    with pytest.raises(ValueError, match="between 1 and 3600"):
        storage.presign_get("private/object.txt", 0)
