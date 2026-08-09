from __future__ import annotations

import base64
import binascii
from hashlib import sha256
from io import BytesIO
from typing import Annotated

from fastapi import Depends
from PIL import Image, UnidentifiedImageError
from pydantic import Field
from zylora_api.core.config import Settings, get_settings
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.templates.schemas import Schema
from zylora_api.storage.base import ObjectStorage
from zylora_api.storage.memory import MemoryObjectStorage
from zylora_api.storage.s3 import S3ObjectStorage

MAX_UPLOAD_BYTES = 8_000_000
MAX_PIXELS = 24_000_000


class AssetUploadRequest(Schema):
    content_base64: Annotated[str, Field(min_length=4, max_length=11_000_000)]
    mime_type: str
    license: Annotated[str, Field(min_length=2, max_length=160)]
    provenance: Annotated[str, Field(min_length=2, max_length=160)]


def get_object_storage(settings: Annotated[Settings, Depends(get_settings)]) -> ObjectStorage:
    if settings.storage_provider == "s3":
        return S3ObjectStorage(settings)
    if settings.storage_provider == "memory":
        return MemoryObjectStorage()
    raise AuthProblem(
        503,
        "storage_unavailable",
        "Asset storage unavailable",
        "Template asset storage is not configured.",
    )


def process_raster(payload: AssetUploadRequest) -> tuple[bytes, int, int, str]:
    if payload.mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise AuthProblem(
            415,
            "asset_type_rejected",
            "Asset rejected",
            "Only PNG, JPEG, and WebP raster images are accepted.",
        )
    try:
        source = base64.b64decode(payload.content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise AuthProblem(
            400, "asset_encoding_invalid", "Asset rejected", "The asset encoding is invalid."
        ) from None
    if not source or len(source) > MAX_UPLOAD_BYTES:
        raise AuthProblem(
            413, "asset_too_large", "Asset rejected", "The asset exceeds the upload limit."
        )
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(BytesIO(source)) as probe:
            probe.verify()
        with Image.open(BytesIO(source)) as image:
            image.load()
            if image.width * image.height > MAX_PIXELS or image.width < 1 or image.height < 1:
                raise ValueError("unsafe dimensions")
            normalized = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            output = BytesIO()
            normalized.save(
                output, format="WEBP", lossless=normalized.mode == "RGBA", quality=88, method=6
            )
            return output.getvalue(), normalized.width, normalized.height, "image/webp"
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise AuthProblem(
            400, "asset_decode_failed", "Asset rejected", "The image could not be safely decoded."
        ) from None


def asset_key(data: bytes) -> tuple[str, str]:
    checksum = sha256(data).hexdigest()
    return f"templates/assets/sha256/{checksum[:2]}/{checksum}.webp", checksum
