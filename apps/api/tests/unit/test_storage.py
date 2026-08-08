import pytest
from zylora_api.storage.keys import validate_object_key
from zylora_api.storage.memory import MemoryObjectStorage


def test_memory_storage_round_trip_and_checksum() -> None:
    storage = MemoryObjectStorage()
    metadata = storage.put_bytes("websites/example/asset.txt", b"zylora", "text/plain")

    assert storage.get_bytes(metadata.key) == b"zylora"
    assert metadata.size == 6
    assert len(metadata.checksum_sha256) == 64

    storage.delete(metadata.key)
    with pytest.raises(KeyError):
        storage.get_bytes(metadata.key)


@pytest.mark.parametrize("key", ["", "/absolute", "../escape", "safe/../escape", "bad\\path"])
def test_object_keys_reject_unsafe_paths(key: str) -> None:
    with pytest.raises(ValueError):
        validate_object_key(key)


def test_memory_storage_never_fabricates_signed_urls() -> None:
    storage = MemoryObjectStorage()
    storage.put_bytes("private/object", b"secret", "application/octet-stream")
    with pytest.raises(RuntimeError, match="does not expose"):
        storage.presign_get("private/object", 60)
