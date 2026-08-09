from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
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


class TemplateCategory(Base):
    __tablename__ = "template_categories"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    active: Mapped[bool] = mapped_column(default=True, server_default="true")


class TemplateTag(Base):
    __tablename__ = "template_tags"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(100))


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','DEPRECATED','RETIRED')", name="ck_templates_status"
        ),
        Index("ix_templates_catalog", "status", "featured_order", "name"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(String(500))
    category_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("template_categories.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    featured_order: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    current_published_version_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TemplateVersion(Base):
    __tablename__ = "template_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','VALIDATING','VALIDATED','REJECTED','APPROVED',"
            "'PUBLISHED','DEPRECATED','RETIRED')",
            name="ck_template_versions_status",
        ),
        UniqueConstraint("template_id", "version", name="uq_template_versions_number"),
        Index("ix_template_versions_template", "template_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    template_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    checksum: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(20))
    registry_version: Mapped[str] = mapped_column(String(20))
    validation_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TemplateValidation(Base):
    __tablename__ = "template_validations"
    __table_args__ = (
        Index("ix_template_validations_version", "template_version_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    template_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("template_versions.id", ondelete="CASCADE")
    )
    checksum: Mapped[str] = mapped_column(String(64))
    validator_version: Mapped[str] = mapped_column(String(20))
    outcome: Mapped[str] = mapped_column(String(20))
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TemplateAsset(Base):
    __tablename__ = "template_assets"
    __table_args__ = (
        CheckConstraint("status IN ('READY','REJECTED')", name="ck_template_assets_status"),
        CheckConstraint(
            "mime_type IN ('image/png','image/jpeg','image/webp')", name="ck_template_assets_mime"
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    status: Mapped[str] = mapped_column(String(20))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(40))
    checksum: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    byte_size: Mapped[int] = mapped_column(Integer)
    license: Mapped[str] = mapped_column(String(160))
    provenance: Mapped[str] = mapped_column(String(160))
    processing_policy: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TemplateTagAssignment(Base):
    __tablename__ = "template_tag_assignments"
    template_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("template_tags.id", ondelete="CASCADE"), primary_key=True
    )
