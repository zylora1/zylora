from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from zylora_api.db.base import Base


class KnowledgeSource(Base):
    """Private, versioned source material belonging to exactly one Website."""

    __tablename__ = "knowledge_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('WEBSITE','PDF','DOCX','TEXT','MARKDOWN')",
            name="ck_knowledge_sources_type",
        ),
        CheckConstraint(
            "status IN ('UPLOADED','SCANNING','PROCESSING','READY','FAILED','DELETED')",
            name="ck_knowledge_sources_status",
        ),
        CheckConstraint("byte_size >= 0", name="ck_knowledge_sources_size"),
        CheckConstraint("version > 0", name="ck_knowledge_sources_version"),
        UniqueConstraint("storage_key", name="uq_knowledge_sources_storage_key"),
        Index("ix_knowledge_sources_website_status", "website_id", "status", "created_at"),
        Index("ix_knowledge_sources_owner_website", "owner_user_id", "website_id"),
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
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_storage_key: Mapped[str | None] = mapped_column(String(1024))
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="UPLOADED")
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message_safe: Mapped[str | None] = mapped_column(String(500))
    extraction_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
