from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
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


class AiSiteProject(Base):
    """Core-owned record for a separately generated Next.js website artifact."""

    __tablename__ = "ai_site_projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','SUBMITTED','PLANNING','GENERATING','VALIDATING',"
            "'READY','FAILED','CANCELLED')",
            name="ck_ai_site_projects_status",
        ),
        UniqueConstraint("owner_user_id", "idempotency_key", name="uq_ai_site_projects_owner_key"),
        Index("ix_ai_site_projects_owner_updated", "owner_user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    prompt_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    prompt_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", server_default="QUEUED")
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    builder_build_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    artifact_digest: Mapped[str | None] = mapped_column(String(128))
    safe_error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiSiteGeneration(Base):
    """Immutable AI website generation/version owned by one project and User."""

    __tablename__ = "ai_site_generations"
    __table_args__ = (
        CheckConstraint(
            "state IN ('CREATED','QUEUED','CLAIMED','GENERATING','VALIDATING','SCANNING',"
            "'SANDBOXING','BUILDING','STORING','COMPLETED','FAILED','CANCELLED')",
            name="ck_ai_site_generations_state",
        ),
        UniqueConstraint("project_id", "version_number", name="uq_ai_generations_project_version"),
        UniqueConstraint("project_id", "request_key", name="uq_ai_generations_project_request"),
        Index("ix_ai_generations_owner_created", "owner_user_id", "created_at"),
        Index("ix_ai_generations_project_created", "project_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_site_projects.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    previous_generation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_site_generations.id", ondelete="RESTRICT")
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    request_key: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    prompt_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="CREATED", server_default="CREATED")
    retryable: Mapped[bool] = mapped_column(default=False, server_default="false")
    error_category: Mapped[str | None] = mapped_column(String(100))
    provider_name: Mapped[str | None] = mapped_column(String(80))
    provider_model: Mapped[str | None] = mapped_column(String(160))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiGenerationJob(Base):
    """Authoritative leased execution record; Celery is delivery, not job state."""

    __tablename__ = "ai_generation_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_ai_generation_jobs_state",
        ),
        CheckConstraint("attempt >= 0 AND max_attempts >= 1", name="ck_ai_jobs_attempts"),
        UniqueConstraint("generation_id", name="uq_ai_jobs_generation"),
        UniqueConstraint("idempotency_key", name="uq_ai_jobs_idempotency"),
        Index("ix_ai_jobs_recovery", "state", "retry_at", "lease_expires_at"),
        Index("ix_ai_jobs_owner_state", "owner_user_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_site_projects.id", ondelete="CASCADE"), nullable=False
    )
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_site_generations.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=4, server_default="4")
    lease_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lease_owner: Mapped[str | None] = mapped_column(String(160))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(100))
    internal_error_detail: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiGenerationArtifact(Base):
    """Immutable, content-addressed generation artifact metadata."""

    __tablename__ = "ai_generation_artifacts"
    __table_args__ = (
        UniqueConstraint("generation_id", name="uq_ai_artifacts_generation"),
        UniqueConstraint("object_key", name="uq_ai_artifacts_object_key"),
        Index("ix_ai_artifacts_owner_created", "owner_user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_site_projects.id", ondelete="CASCADE"), nullable=False
    )
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_site_generations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiGenerationEvent(Base):
    """Append-only safe transition/operational evidence for observability."""

    __tablename__ = "ai_generation_events"
    __table_args__ = (Index("ix_ai_generation_events_timeline", "generation_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_site_generations.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_generation_jobs.id", ondelete="SET NULL")
    )
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
