from __future__ import annotations

from typing import NoReturn

from zylora_api.core.config import Settings
from zylora_api.storage.base import ObjectMetadata, ObjectStorage
from zylora_api.storage.memory import MemoryObjectStorage
from zylora_api.storage.s3 import S3ObjectStorage


class DisabledPublicationStorage:
    """Fail-closed adapter used until immutable artifact storage is configured."""

    @staticmethod
    def _raise() -> NoReturn:
        raise RuntimeError("Immutable publication artifact storage is not configured.")

    def check(self) -> bool:
        return False

    def put_bytes(self, key: str, data: bytes, content_type: str) -> ObjectMetadata:
        self._raise()

    def get_bytes(self, key: str) -> bytes:
        self._raise()

    def delete(self, key: str) -> None:
        self._raise()

    def presign_get(self, key: str, expires_seconds: int) -> str:
        self._raise()


def publication_storage_for(settings: Settings) -> ObjectStorage:
    if settings.storage_provider == "s3":
        return S3ObjectStorage(settings)
    if settings.storage_provider == "memory" and settings.environment == "test":
        return MemoryObjectStorage()
    return DisabledPublicationStorage()
