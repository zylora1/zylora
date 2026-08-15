from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from zylora_api.db.base import Base


class WhatsAppNotificationSetting(Base):
    __tablename__ = "whatsapp_notification_settings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DISABLED','READY','NEEDS_ATTENTION')",
            name="ck_whatsapp_settings_status",
        ),
        UniqueConstraint("owner_user_id", name="uq_whatsapp_settings_owner"),
        UniqueConstraint("phone_hash", name="uq_whatsapp_settings_phone_hash"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    phone_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    phone_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    phone_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="DISABLED")
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WhatsAppNotification(Base):
    __tablename__ = "whatsapp_notifications"
    __table_args__ = (
        CheckConstraint("kind IN ('LEAD_OWNER_ALERT','TEST')", name="ck_whatsapp_kind"),
        CheckConstraint(
            "state IN ('QUEUED','SENDING','RETRY_WAIT','SENT','DELIVERED',"
            "'READ','FAILED','SUPPRESSED')",
            name="ck_whatsapp_state",
        ),
        UniqueConstraint("idempotency_key", name="uq_whatsapp_idempotency"),
        UniqueConstraint("provider_message_sid", name="uq_whatsapp_provider_sid"),
        Index("ix_whatsapp_dispatch", "state", "next_attempt_at", "created_at"),
        Index("ix_whatsapp_owner_created", "owner_user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    website_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="RESTRICT")
    )
    lead_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="RESTRICT")
    )
    setting_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp_notification_settings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    template_content_sid: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, server_default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    provider_message_sid: Mapped[str | None] = mapped_column(String(80))
    provider_status: Mapped[str | None] = mapped_column(String(40))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_detail_safe: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WhatsAppCallbackEvent(Base):
    __tablename__ = "whatsapp_callback_events"
    __table_args__ = (
        UniqueConstraint("event_digest", name="uq_whatsapp_callback_digest"),
        Index("ix_whatsapp_callback_message", "provider_message_sid", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    notification_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("whatsapp_notifications.id", ondelete="RESTRICT")
    )
    provider_message_sid: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_status: Mapped[str] = mapped_column(String(40), nullable=False)
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processing_outcome: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
