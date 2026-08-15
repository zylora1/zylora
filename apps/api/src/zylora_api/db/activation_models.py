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


class ProductEvent(Base):
    __tablename__ = "product_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_product_events_idempotency"),
        Index("ix_product_events_type_time", "event_type", "occurred_at"),
        Index("ix_product_events_user_time", "user_id", "occurred_at"),
        Index("ix_product_events_website_time", "website_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    website_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="RESTRICT")
    )
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WebsiteValueState(Base):
    __tablename__ = "website_value_states"
    __table_args__ = (
        UniqueConstraint("website_id", name="uq_website_value_states_website"),
        Index("ix_website_value_states_owner", "owner_user_id", "published_at"),
        Index("ix_website_value_states_first_lead", "first_lead_at"),
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
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_visitor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_lead_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AcquisitionAttribution(Base):
    __tablename__ = "acquisition_attributions"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_acquisition_attributions_user"),
        Index("ix_acquisition_attributions_source_time", "normalized_source", "captured_at"),
        Index("ix_acquisition_attributions_country_time", "country_code", "captured_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    normalized_source: Mapped[str] = mapped_column(String(32), nullable=False)
    signup_source: Mapped[str] = mapped_column(String(24), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, server_default="ZZ")
    utm_source: Mapped[str | None] = mapped_column(String(160))
    utm_medium: Mapped[str | None] = mapped_column(String(160))
    utm_campaign: Mapped[str | None] = mapped_column(String(200))
    utm_content: Mapped[str | None] = mapped_column(String(200))
    utm_term: Mapped[str | None] = mapped_column(String(200))
    referrer: Mapped[str | None] = mapped_column(String(1000))
    landing_page: Mapped[str | None] = mapped_column(String(1000))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WebsiteDigestDelivery(Base):
    __tablename__ = "website_digest_deliveries"
    __table_args__ = (
        CheckConstraint("channel IN ('EMAIL','WHATSAPP')", name="ck_digest_deliveries_channel"),
        CheckConstraint(
            "state IN ('PENDING','SENT','FAILED','SKIPPED')", name="ck_digest_deliveries_state"
        ),
        UniqueConstraint(
            "website_id", "digest_month", "channel", name="uq_digest_deliveries_period"
        ),
        Index("ix_digest_deliveries_dispatch", "state", "created_at"),
        Index("ix_digest_deliveries_owner", "owner_user_id", "digest_month"),
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
    digest_month: Mapped[str] = mapped_column(String(7), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    transactional_email_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("transactional_emails.id", ondelete="RESTRICT")
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(100))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ZeroLeadCheckpoint(Base):
    __tablename__ = "zero_lead_checkpoints"
    __table_args__ = (
        CheckConstraint("checkpoint_days IN (14,30)", name="ck_zero_lead_checkpoint_days"),
        CheckConstraint(
            "state IN ('PENDING','NOTIFIED','SKIPPED')", name="ck_zero_lead_checkpoint_state"
        ),
        UniqueConstraint(
            "website_id", "publication_at", "checkpoint_days", name="uq_zero_lead_checkpoint"
        ),
        Index("ix_zero_lead_checkpoint_owner", "owner_user_id", "created_at"),
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
    publication_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checkpoint_days: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    notification_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("notifications.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
