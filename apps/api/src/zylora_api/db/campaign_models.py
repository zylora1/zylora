# ruff: noqa: E501
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


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(
            "state IN ('DRAFT','READY','SCHEDULED','SENDING','COMPLETED','PAUSED','CANCELLED','FAILED')",
            name="ck_campaigns_state",
        ),
        CheckConstraint(
            "audience_type IN ('ALL_USERS','FREE_USERS','PAID_USERS','PLAN_USERS','RECENT_USERS','HAS_DRAFT','NO_PUBLISHED_WEBSITE')",
            name="ck_campaigns_audience",
        ),
        CheckConstraint(
            "(audience_type = 'PLAN_USERS' AND audience_plan_code IN ('FREE','BASIC','GROWTH','BUSINESS')) OR (audience_type <> 'PLAN_USERS' AND audience_plan_code IS NULL)",
            name="ck_campaigns_plan_audience",
        ),
        Index("ix_campaigns_state_schedule", "state", "scheduled_at", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="DRAFT")
    audience_type: Mapped[str] = mapped_column(String(32), nullable=False)
    audience_plan_code: Mapped[str | None] = mapped_column(String(20))
    audience_snapshot_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING','SUPPRESSED','SENDING','SENT','DELIVERED','FAILED','BOUNCED','COMPLAINED','UNSUBSCRIBED')",
            name="ck_campaign_recipients_state",
        ),
        UniqueConstraint("campaign_id", "recipient_user_id", name="uq_campaign_recipients_user"),
        UniqueConstraint("idempotency_key", name="uq_campaign_recipients_idempotency"),
        UniqueConstraint("unsubscribe_token_digest", name="uq_campaign_recipients_unsubscribe"),
        Index("ix_campaign_recipients_delivery", "campaign_id", "state", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    recipient_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recipient_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    unsubscribe_token_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    unsubscribe_token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    suppression_reason: Mapped[str | None] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmailSuppression(Base):
    __tablename__ = "email_suppressions"
    __table_args__ = (
        CheckConstraint("scope IN ('MARKETING','ALL_EMAIL')", name="ck_email_suppressions_scope"),
        UniqueConstraint("recipient_user_id", "scope", name="uq_email_suppressions_user_scope"),
        Index("ix_email_suppressions_scope", "scope", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    recipient_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default="MARKETING")
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CampaignDeliveryEvent(Base):
    __tablename__ = "campaign_delivery_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('ACCEPTED','DELIVERED','BOUNCED','COMPLAINED','OPENED','CLICKED','UNSUBSCRIBED','FAILED')",
            name="ck_campaign_delivery_events_type",
        ),
        UniqueConstraint(
            "provider", "provider_event_id", name="uq_campaign_delivery_events_provider"
        ),
        Index("ix_campaign_delivery_events_recipient", "campaign_recipient_id", "occurred_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    campaign_recipient_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaign_recipients.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
