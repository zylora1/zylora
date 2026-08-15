from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    key: str
    size: int
    content_type: str
    checksum_sha256: str


class ObjectStorage(Protocol):
    def check(self) -> bool: ...

    def put_bytes(self, key: str, data: bytes, content_type: str) -> ObjectMetadata: ...

    def get_bytes(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def presign_get(self, key: str, expires_seconds: int) -> str: ...
