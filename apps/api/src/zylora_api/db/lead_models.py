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


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint("source IN ('FORM','CHATBOT')", name="ck_leads_source"),
        CheckConstraint(
            "status IN ('NEW','CONTACTED','QUALIFIED','ARCHIVED')", name="ck_leads_status"
        ),
        UniqueConstraint("website_id", "source", "idempotency_key", name="uq_leads_idempotency"),
        Index("ix_leads_owner_captured", "owner_user_id", "captured_at"),
        Index("ix_leads_website_source", "website_id", "source", "captured_at"),
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
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_reference_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(80))
    enquiry: Mapped[str] = mapped_column(Text, nullable=False)
    page_path: Mapped[str | None] = mapped_column(String(1024))
    consent: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="NEW")
    whatsapp_notification_queued: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LeadCreditAccount(Base):
    __tablename__ = "lead_credit_accounts"
    __table_args__ = (CheckConstraint("version > 0", name="ck_lead_credit_accounts_version"),)
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LeadCreditLedger(Base):
    __tablename__ = "lead_credit_ledger"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('PURCHASE','LEAD_CAPTURE','ADMIN_GRANT','REFUND','CORRECTION')",
            name="ck_lead_credit_ledger_type",
        ),
        CheckConstraint("delta <> 0", name="ck_lead_credit_ledger_delta"),
        CheckConstraint(
            "(entry_type <> 'LEAD_CAPTURE') OR (delta = -1 AND lead_id IS NOT NULL)",
            name="ck_lead_credit_ledger_lead_capture",
        ),
        UniqueConstraint("user_id", "idempotency_key", name="uq_lead_credit_ledger_idempotency"),
        Index(
            "uq_lead_credit_ledger_lead",
            "lead_id",
            unique=True,
            postgresql_where=text("lead_id IS NOT NULL"),
        ),
        Index("ix_lead_credit_ledger_user_created", "user_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    lead_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="RESTRICT")
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    entry_type: Mapped[str] = mapped_column(String(24), nullable=False)
    delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resulting_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("state IN ('QUEUED','READ','ARCHIVED')", name="ck_notifications_state"),
        UniqueConstraint("recipient_user_id", "dedupe_key", name="uq_notifications_dedupe"),
        Index("ix_notifications_recipient_time", "recipient_user_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    recipient_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="QUEUED")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        UniqueConstraint("website_id", "idempotency_key", name="uq_analytics_events_idempotency"),
        Index("ix_analytics_events_website_time", "website_id", "occurred_at"),
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
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
