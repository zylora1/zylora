from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field
from zylora_api.modules.commerce.schemas import Schema


class DomainCreateRequest(Schema):
    hostname: str = Field(min_length=3, max_length=253)


class DomainResponse(Schema):
    id: UUID
    website_id: UUID
    type: Literal["ZYLORA_SUBDOMAIN", "CUSTOM"]
    hostname: str
    state: str
    tls_status: str
    is_primary: bool
    is_active: bool
    verification_record_name: str | None
    verification_record_type: str | None
    verification_record_value: str | None
    safe_error: str | None
    updated_at: datetime


class DeploymentResponse(Schema):
    id: UUID
    website_id: UUID
    domain_id: UUID
    operation: Literal["PUBLISH", "ROLLBACK"]
    state: str
    artifact_checksum: str | None
    failure_code: str | None
    safe_error: str | None
    queued_at: datetime
    completed_at: datetime | None


class PublicationStatusResponse(Schema):
    website_id: UUID
    website_status: str
    active_deployment_id: UUID | None
    domains: list[DomainResponse]
    deployments: list[DeploymentResponse]


class RollbackRequest(Schema):
    deployment_id: UUID
