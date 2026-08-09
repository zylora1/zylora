from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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


class Website(Base):
    __tablename__ = "websites"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','TRANSFER_PENDING','ARCHIVED')",
            name="ck_websites_status",
        ),
        Index("ix_websites_owner_status", "owner_user_id", "status", "updated_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    source_template_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", server_default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WebsitePage(Base):
    __tablename__ = "website_pages"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','HIDDEN','ARCHIVED')", name="ck_website_pages_status"),
        CheckConstraint(
            "parent_page_id IS NULL OR parent_page_id <> id",
            name="ck_website_pages_not_self_parent",
        ),
        CheckConstraint(
            "(is_home AND parent_page_id IS NULL AND slug = '') OR (NOT is_home AND slug <> '')",
            name="ck_website_pages_home_shape",
        ),
        UniqueConstraint("id", "website_id", name="uq_website_pages_id_website"),
        ForeignKeyConstraint(
            ["parent_page_id", "website_id"],
            ["website_pages.id", "website_pages.website_id"],
            ondelete="RESTRICT",
            name="fk_website_pages_parent_same_website",
        ),
        Index("ix_website_pages_navigation", "website_id", "parent_page_id", "sort_order"),
        Index(
            "uq_website_pages_one_home", "website_id", unique=True, postgresql_where=text("is_home")
        ),
        Index(
            "uq_website_pages_sibling_slug",
            "website_id",
            text("coalesce(parent_page_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "slug",
            unique=True,
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="CASCADE"), nullable=False
    )
    source_template_page_id: Mapped[str] = mapped_column(String(64))
    parent_page_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_home: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    show_in_navigation: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    seo: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WebsitePagePathChange(Base):
    __tablename__ = "website_page_path_changes"
    __table_args__ = (
        CheckConstraint("old_path <> new_path", name="ck_website_page_path_changes_distinct"),
        Index("ix_website_page_path_changes_lookup", "website_id", "old_path", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    old_path: Mapped[str] = mapped_column(String(1536), nullable=False)
    new_path: Mapped[str] = mapped_column(String(1536), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
