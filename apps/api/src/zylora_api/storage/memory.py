from __future__ import annotations

from hashlib import sha256

from zylora_api.storage.base import ObjectMetadata
from zylora_api.storage.keys import validate_object_key


class MemoryObjectStorage:
    """Deterministic test adapter; production configuration cannot select it."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, ObjectMetadata]] = {}

    def check(self) -> bool:
        return True

    def put_bytes(self, key: str, data: bytes, content_type: str) -> ObjectMetadata:
        normalized = validate_object_key(key)
        metadata = ObjectMetadata(
            key=normalized,
            size=len(data),
            content_type=content_type,
            checksum_sha256=sha256(data).hexdigest(),
        )
        self._objects[normalized] = (bytes(data), metadata)
        return metadata

    def get_bytes(self, key: str) -> bytes:
        normalized = validate_object_key(key)
        return self._objects[normalized][0]

    def delete(self, key: str) -> None:
        normalized = validate_object_key(key)
        self._objects.pop(normalized, None)

    def presign_get(self, key: str, expires_seconds: int) -> str:
        validate_object_key(key)
        if not 1 <= expires_seconds <= 3600:
            raise ValueError("test signed URL expiry must be between 1 and 3600 seconds")
        raise RuntimeError("memory storage does not expose download URLs")
