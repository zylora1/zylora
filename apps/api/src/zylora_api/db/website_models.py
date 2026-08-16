# ruff: noqa: E501
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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


class Website(Base):
    __tablename__ = "websites"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHING','PUBLISHED','UNPUBLISHING','UNPUBLISHED','TRANSFER_PENDING','TRANSFERRED','ARCHIVED','FAILED')",
            name="ck_websites_status",
        ),
        CheckConstraint(
            "publication_domain_type IS NULL OR publication_domain_type IN ('ZYLORA_SUBDOMAIN','CUSTOM')",
            name="ck_websites_publication_domain_type",
        ),
        Index("ix_websites_owner_status", "owner_user_id", "status", "updated_at"),
        CheckConstraint(
            "(status IN ('PUBLISHING','PUBLISHED','UNPUBLISHING') AND live_owner_user_id IS NOT NULL) OR "
            "(status NOT IN ('PUBLISHING','PUBLISHED','UNPUBLISHING') AND live_owner_user_id IS NULL)",
            name="ck_websites_live_owner_state",
        ),
        Index(
            "uq_websites_one_live_owner",
            "live_owner_user_id",
            unique=True,
            postgresql_where=text("live_owner_user_id IS NOT NULL"),
        ),
        CheckConstraint(
            "site_origin IN ('TEMPLATE','AI')",
            name="ck_websites_site_origin",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    live_owner_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    source_template_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    site_origin: Mapped[str] = mapped_column(
        String(16), nullable=False, default="TEMPLATE", server_default="TEMPLATE"
    )
    display_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", server_default="DRAFT")
    theme: Mapped[dict[str, Any]] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    current_version_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("website_versions.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_version_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("website_versions.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    active_deployment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    publication_domain_type: Mapped[str | None] = mapped_column(String(24))
    publish_request_idempotency_key: Mapped[str | None] = mapped_column(String(160))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WebsiteOwnership(Base):
    __tablename__ = "website_ownerships"
    __table_args__ = (
        CheckConstraint(
            "acquisition_reason IN ('TEMPLATE_CREATION','TRANSFER')",
            name="ck_website_ownerships_reason",
        ),
        Index(
            "uq_website_ownerships_current",
            "website_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index("ix_website_ownerships_owner_time", "owner_user_id", "started_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transfer_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ownership_transfers.id", ondelete="RESTRICT", use_alter=True),
    )
    acquisition_reason: Mapped[str] = mapped_column(String(32), nullable=False)


class OwnershipTransfer(Base):
    __tablename__ = "ownership_transfers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('REQUESTED','VALIDATED','DEACTIVATING','COMPLETED','FAILED','CANCELLED')",
            name="ck_ownership_transfers_status",
        ),
        UniqueConstraint(
            "sender_user_id", "idempotency_key", name="uq_ownership_transfers_idempotency"
        ),
        Index("ix_ownership_transfers_website_time", "website_id", "created_at"),
        Index(
            "uq_ownership_transfers_active_website",
            "website_id",
            unique=True,
            postgresql_where=text("status IN ('REQUESTED','VALIDATED','DEACTIVATING')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="RESTRICT"), nullable=False
    )
    sender_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recipient_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    confirmation_version: Mapped[str | None] = mapped_column(String(40))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class AiOperation(Base):
    __tablename__ = "ai_operations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PLANNING','SUCCEEDED','FAILED')",
            name="ck_ai_operations_status",
        ),
        CheckConstraint("scope IN ('PAGE','WEBSITE')", name="ck_ai_operations_scope"),
        CheckConstraint("cost_credits >= 0", name="ck_ai_operations_cost"),
        Index("ix_ai_operations_owner_time", "user_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    selected_page_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    prompt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result_revision: Mapped[int | None] = mapped_column(Integer)
    cost_credits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    operation_summary: Mapped[str | None] = mapped_column(String(240))
    error_code: Mapped[str | None] = mapped_column(String(100))
    safe_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebsiteVersion(Base):
    __tablename__ = "website_versions"
    __table_args__ = (
        CheckConstraint(
            "source IN ('TEMPLATE','MANUAL','AI','RESTORE','SYSTEM_MIGRATION')",
            name="ck_website_versions_source",
        ),
        CheckConstraint(
            "validation_status IN ('VALID')",
            name="ck_website_versions_validation_status",
        ),
        UniqueConstraint("website_id", "revision", name="uq_website_versions_revision"),
        UniqueConstraint("website_id", "operation_id", name="uq_website_versions_operation"),
        Index("ix_website_versions_history", "website_id", "revision"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="CASCADE"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("website_versions.id", ondelete="RESTRICT")
    )
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    page_state: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    operation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    ai_operation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_operations.id", ondelete="RESTRICT")
    )
    edit_summary: Mapped[str] = mapped_column(String(240), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiCreditAccount(Base):
    __tablename__ = "ai_credit_accounts"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_ai_credit_accounts_balance"),
        CheckConstraint("allowance >= 0", name="ck_ai_credit_accounts_allowance"),
        CheckConstraint("period_end > period_start", name="ck_ai_credit_accounts_period"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False)
    allowance: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiCreditLedger(Base):
    __tablename__ = "ai_credit_ledger"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('MONTHLY_GRANT','AI_EDIT','ADJUSTMENT')",
            name="ck_ai_credit_ledger_type",
        ),
        CheckConstraint("resulting_balance >= 0", name="ck_ai_credit_ledger_balance"),
        UniqueConstraint("user_id", "operation_id", name="uq_ai_credit_ledger_operation"),
        Index("ix_ai_credit_ledger_owner_time", "user_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    operation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(24), nullable=False)
    resulting_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
