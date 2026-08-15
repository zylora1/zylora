from pathlib import PurePosixPath


def validate_object_key(key: str) -> str:
    if not key or key.startswith(("/", "\\")) or "\\" in key or "\x00" in key:
        raise ValueError("object key must be a non-empty relative POSIX path")
    path = PurePosixPath(key)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("object key contains an unsafe path segment")
    normalized = path.as_posix()
    if len(normalized) > 1024:
        raise ValueError("object key exceeds the maximum length")
    return normalized
