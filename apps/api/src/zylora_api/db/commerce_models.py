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


class PlanCatalog(Base):
    __tablename__ = "plan_catalogs"
    __table_args__ = (
        CheckConstraint("region IN ('INDIA','INTERNATIONAL')", name="ck_plan_catalogs_region"),
        CheckConstraint("currency IN ('INR','USD')", name="ck_plan_catalogs_currency"),
        CheckConstraint("interval = 'MONTHLY'", name="ck_plan_catalogs_interval"),
        CheckConstraint(
            "status IN ('DRAFT','VALIDATED','PUBLISHED','RETIRED','REJECTED')",
            name="ck_plan_catalogs_status",
        ),
        UniqueConstraint("region", "interval", "version", name="uq_plan_catalogs_version"),
        Index(
            "uq_plan_catalogs_current",
            "region",
            "interval",
            unique=True,
            postgresql_where=text("status = 'PUBLISHED'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("code IN ('FREE','BASIC','GROWTH','BUSINESS')", name="ck_plans_code"),
        CheckConstraint("slot BETWEEN 1 AND 4", name="ck_plans_slot"),
        UniqueConstraint("catalog_id", "code", name="uq_plans_catalog_code"),
        UniqueConstraint("catalog_id", "slot", name="uq_plans_catalog_slot"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    catalog_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plan_catalogs.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    most_popular: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanPrice(Base):
    __tablename__ = "plan_prices"
    __table_args__ = (
        CheckConstraint("amount_minor >= 0", name="ck_plan_prices_amount"),
        CheckConstraint("currency IN ('INR','USD')", name="ck_plan_prices_currency"),
        CheckConstraint("interval = 'MONTHLY'", name="ck_plan_prices_interval"),
        UniqueConstraint("plan_id", "currency", "interval", name="uq_plan_prices_plan_currency"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (
        CheckConstraint(
            "value_type IN ('BOOLEAN','INTEGER','ENUM','UNLIMITED')",
            name="ck_plan_entitlements_type",
        ),
        CheckConstraint(
            "(value_type = 'BOOLEAN' AND value_bool IS NOT NULL AND value_int IS NULL AND value_text IS NULL) OR "
            "(value_type = 'INTEGER' AND value_bool IS NULL AND value_int IS NOT NULL AND value_text IS NULL) OR "
            "(value_type IN ('ENUM','UNLIMITED') AND value_bool IS NULL AND value_int IS NULL AND value_text IS NOT NULL)",
            name="ck_plan_entitlements_one_value",
        ),
        UniqueConstraint("plan_id", "capability_key", name="uq_plan_entitlements_capability"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    capability_key: Mapped[str] = mapped_column(String(80), nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False)
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    value_int: Mapped[int | None] = mapped_column(Integer)
    value_text: Mapped[str | None] = mapped_column(String(80))
    unit: Mapped[str | None] = mapped_column(String(32))


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING','AUTHENTICATING','ACTIVE','RENEWAL_PENDING','PAST_DUE','CANCELLED','EXPIRED','FAILED')",
            name="ck_subscriptions_state",
        ),
        CheckConstraint("amount_minor >= 0", name="ck_subscriptions_amount"),
        CheckConstraint("currency IN ('INR','USD')", name="ck_subscriptions_currency"),
        CheckConstraint("interval = 'MONTHLY'", name="ck_subscriptions_interval"),
        CheckConstraint(
            "current_period_end > current_period_start", name="ck_subscriptions_period"
        ),
        Index(
            "uq_subscriptions_current_user",
            "user_id",
            unique=True,
            postgresql_where=text(
                "state IN ('PENDING','AUTHENTICATING','ACTIVE','RENEWAL_PENDING','PAST_DUE','CANCELLED')"
            ),
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    catalog_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plan_catalogs.id", ondelete="RESTRICT"), nullable=False
    )
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    price_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plan_prices.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    plan_code_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    entitlements_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, server_default="false")
    scheduled_plan_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT")
    )
    scheduled_price_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plan_prices.id", ondelete="RESTRICT")
    )
    provider_customer_reference: Mapped[str | None] = mapped_column(String(200))
    provider_subscription_reference: Mapped[str | None] = mapped_column(String(200))
    last_trusted_payment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT", use_alter=True)
    )
    version: Mapped[int] = mapped_column(BigInteger, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("purpose IN ('SUBSCRIPTION','EXPORT')", name="ck_payments_purpose"),
        CheckConstraint(
            "state IN ('CREATED','PENDING','PROCESSING','CAPTURED','SETTLED','FAILED','CANCELLED','REFUND_PENDING','REFUNDED','PARTIALLY_REFUNDED')",
            name="ck_payments_state",
        ),
        CheckConstraint("expected_amount_minor >= 0", name="ck_payments_amount"),
        CheckConstraint("expected_currency IN ('INR','USD')", name="ck_payments_currency"),
        CheckConstraint(
            "(purpose = 'SUBSCRIPTION' AND plan_id IS NOT NULL AND price_id IS NOT NULL AND export_purchase_id IS NULL) OR "
            "(purpose = 'EXPORT' AND plan_id IS NULL AND price_id IS NULL AND export_purchase_id IS NOT NULL)",
            name="ck_payments_purpose_reference",
        ),
        UniqueConstraint("user_id", "idempotency_key", name="uq_payments_user_idempotency"),
        Index(
            "uq_payments_export_purchase",
            "export_purchase_id",
            unique=True,
            postgresql_where=text("export_purchase_id IS NOT NULL"),
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    plan_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT")
    )
    price_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plan_prices.id", ondelete="RESTRICT")
    )
    export_purchase_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("export_purchases.id", ondelete="RESTRICT")
    )
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    expected_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_payment_reference: Mapped[str | None] = mapped_column(String(200), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    trusted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_payment_events_provider_event"),
        Index("ix_payment_events_payment_time", "payment_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    payment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processing_outcome: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExportPrice(Base):
    __tablename__ = "export_prices"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_export_prices_amount"),
        CheckConstraint("currency IN ('INR','USD')", name="ck_export_prices_currency"),
        CheckConstraint("version > 0", name="ck_export_prices_version"),
        UniqueConstraint("currency", "version", name="uq_export_prices_currency_version"),
        Index(
            "uq_export_prices_active_currency",
            "currency",
            unique=True,
            postgresql_where=text("active"),
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    configured_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExportPurchase(Base):
    __tablename__ = "export_purchases"
    __table_args__ = (
        CheckConstraint(
            "state IN ('CREATED','PAYMENT_PENDING','PAID','GENERATING','READY','FAILED','EXPIRED','REFUNDED')",
            name="ck_export_purchases_state",
        ),
        CheckConstraint("amount_minor > 0", name="ck_export_purchases_amount"),
        CheckConstraint("currency IN ('INR','USD')", name="ck_export_purchases_currency"),
        CheckConstraint("price_version > 0", name="ck_export_purchases_price_version"),
        UniqueConstraint(
            "owner_user_id", "idempotency_key", name="uq_export_purchases_idempotency"
        ),
        Index("ix_export_purchases_owner_time", "owner_user_id", "created_at"),
        Index("ix_export_purchases_website_state", "website_id", "state", "created_at"),
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
    website_version_checksum: Mapped[str] = mapped_column(String(80), nullable=False)
    export_price_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("export_prices.id", ondelete="RESTRICT"), nullable=False
    )
    price_version: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, server_default="CREATED")
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    safe_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WebsiteExportArtifact(Base):
    __tablename__ = "website_export_artifacts"
    __table_args__ = (
        CheckConstraint("byte_size > 0", name="ck_website_export_artifacts_size"),
        CheckConstraint("download_count >= 0", name="ck_website_export_artifacts_download_count"),
        UniqueConstraint("purchase_id", name="uq_website_export_artifacts_purchase"),
        UniqueConstraint("object_key", name="uq_website_export_artifacts_object_key"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    purchase_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("export_purchases.id", ondelete="RESTRICT"), nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("total_minor >= 0", name="ck_invoices_total"),
        CheckConstraint("currency IN ('INR','USD')", name="ck_invoices_currency"),
        CheckConstraint("state IN ('ISSUED','PAID','VOID')", name="ck_invoices_state"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    subscription_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=False
    )
    payment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationQuotaAccount(Base):
    __tablename__ = "notification_quota_accounts"
    __table_args__ = (
        CheckConstraint("channel = 'WHATSAPP'", name="ck_notification_quota_channel"),
        CheckConstraint(
            "used >= 0 AND allowance >= 0 AND used <= allowance", name="ck_notification_quota_usage"
        ),
        CheckConstraint("period_end > period_start", name="ck_notification_quota_period"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    channel: Mapped[str] = mapped_column(String(20), primary_key=True)
    used: Mapped[int] = mapped_column(Integer, nullable=False)
    allowance: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NotificationQuotaLedger(Base):
    __tablename__ = "notification_quota_ledger"
    __table_args__ = (
        CheckConstraint("channel = 'WHATSAPP'", name="ck_notification_quota_ledger_channel"),
        CheckConstraint("delta = 1", name="ck_notification_quota_ledger_delta"),
        CheckConstraint("resulting_used >= 0", name="ck_notification_quota_ledger_result"),
        UniqueConstraint(
            "user_id", "channel", "operation_id", name="uq_notification_quota_operation"
        ),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    operation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_used: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
