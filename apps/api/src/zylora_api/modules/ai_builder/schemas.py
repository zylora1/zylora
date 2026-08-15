from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AiSiteProjectCreate(Schema):
    prompt: str = Field(min_length=20, max_length=2000)


class AiSiteProjectResponse(Schema):
    id: UUID
    status: str
    generation_id: UUID
    generation_version: int
    attempt: int
    max_attempts: int
    retryable: bool
    can_cancel: bool
    can_retry: bool
    preview_ready: bool
    artifact_digest: str | None
    safe_error_code: str | None
    safe_error_message: str | None
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AiSiteProjectListResponse(Schema):
    items: list[AiSiteProjectResponse]


class AiArtifactAccessResponse(Schema):
    generation_id: UUID
    checksum_sha256: str
    size_bytes: int
    content_type: str
    download_url: str
    expires_in_seconds: int
