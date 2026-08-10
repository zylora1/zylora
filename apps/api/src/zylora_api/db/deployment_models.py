# ruff: noqa: E501
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from zylora_api.db.base import Base


class Domain(Base):
    __tablename__ = "domains"
    __table_args__ = (
        CheckConstraint("type IN ('ZYLORA_SUBDOMAIN','CUSTOM')", name="ck_domains_type"),
        CheckConstraint(
            "state IN ('RESERVED','PENDING_DNS','VERIFIED','VERIFICATION_FAILED','PROVISIONING','ACTIVE','DEGRADED','DEACTIVATING','INACTIVE','PROVISIONING_FAILED')",
            name="ck_domains_state",
        ),
        CheckConstraint(
            "tls_status IN ('PENDING','ACTIVE','FAILED','UNKNOWN')", name="ck_domains_tls_status"
        ),
        CheckConstraint(
            "NOT is_active OR state IN ('ACTIVE','DEGRADED')", name="ck_domains_active_state"
        ),
        UniqueConstraint("hostname", name="uq_domains_hostname"),
        Index("ix_domains_website_state", "website_id", "state", "updated_at"),
        Index(
            "uq_domains_primary_live_website",
            "website_id",
            unique=True,
            postgresql_where=text("is_primary AND state IN ('PROVISIONING','ACTIVE','DEGRADED')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="RESTRICT"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    display_hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, server_default="RESERVED")
    verification_record_name: Mapped[str | None] = mapped_column(String(253))
    verification_record_type: Mapped[str | None] = mapped_column(String(12))
    verification_record_value: Mapped[str | None] = mapped_column(Text)
    provider_hostname_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    provider_reference: Mapped[str | None] = mapped_column(String(253))
    tls_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    safe_error: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        CheckConstraint("operation IN ('PUBLISH','ROLLBACK')", name="ck_deployments_operation"),
        CheckConstraint(
            "state IN ('QUEUED','VALIDATING','BUILDING','PROVISIONING','HEALTH_CHECKING','SWITCHING','ACTIVE','SUPERSEDED','ROLLING_BACK','FAILED','CANCELLED')",
            name="ck_deployments_state",
        ),
        UniqueConstraint(
            "website_id", "idempotency_key", name="uq_deployments_website_idempotency"
        ),
        Index("ix_deployments_website_queued", "website_id", "queued_at"),
        Index(
            "uq_deployments_active_attempt",
            "website_id",
            unique=True,
            postgresql_where=text(
                "state IN ('QUEUED','VALIDATING','BUILDING','PROVISIONING','HEALTH_CHECKING','SWITCHING','ROLLING_BACK')"
            ),
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="RESTRICT"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    website_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("website_versions.id", ondelete="RESTRICT"), nullable=False
    )
    domain_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("domains.id", ondelete="RESTRICT"), nullable=False
    )
    previous_deployment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("deployments.id", ondelete="RESTRICT")
    )
    operation: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PUBLISH")
    state: Mapped[str] = mapped_column(String(32), nullable=False, server_default="QUEUED")
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    artifact_key: Mapped[str | None] = mapped_column(String(1024))
    artifact_checksum: Mapped[str | None] = mapped_column(String(64))
    provider_route_reference: Mapped[str | None] = mapped_column(String(253))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    safe_error: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    switched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeploymentEvent(Base):
    __tablename__ = "deployment_events"
    __table_args__ = (
        CheckConstraint("to_state <> ''", name="ck_deployment_events_to_state"),
        Index("ix_deployment_events_deployment_time", "deployment_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    deployment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("deployments.id", ondelete="RESTRICT"), nullable=False
    )
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(160))
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
