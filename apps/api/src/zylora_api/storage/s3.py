from __future__ import annotations

from hashlib import sha256
from typing import Any

import boto3
from botocore.config import Config

from zylora_api.core.config import Settings
from zylora_api.storage.base import ObjectMetadata
from zylora_api.storage.keys import validate_object_key


class S3ObjectStorage:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if settings.storage_provider != "s3":
            raise ValueError("S3 adapter requires storage_provider=s3")
        self._bucket = settings.s3_bucket
        self._client = client or boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"}
            ),
        )

    def check(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            return False

    def put_bytes(self, key: str, data: bytes, content_type: str) -> ObjectMetadata:
        normalized = validate_object_key(key)
        checksum = sha256(data).hexdigest()
        self._client.put_object(
            Bucket=self._bucket,
            Key=normalized,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": checksum},
            ServerSideEncryption="AES256",
        )
        return ObjectMetadata(normalized, len(data), content_type, checksum)

    def get_bytes(self, key: str) -> bytes:
        normalized = validate_object_key(key)
        response = self._client.get_object(Bucket=self._bucket, Key=normalized)
        return bytes(response["Body"].read())

    def delete(self, key: str) -> None:
        normalized = validate_object_key(key)
        self._client.delete_object(Bucket=self._bucket, Key=normalized)

    def presign_get(self, key: str, expires_seconds: int) -> str:
        normalized = validate_object_key(key)
        if not 1 <= expires_seconds <= 3600:
            raise ValueError("signed URL expiry must be between 1 and 3600 seconds")
        return str(
            self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": normalized},
                ExpiresIn=expires_seconds,
            )
        )
