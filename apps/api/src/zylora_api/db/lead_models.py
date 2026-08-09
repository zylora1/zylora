from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from zylora_api.db.base import Base


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint("source IN ('FORM','CHATBOT')", name="ck_leads_source"),
        UniqueConstraint("website_id", "source", "idempotency_key", name="uq_leads_idempotency"),
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
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(80))
    enquiry: Mapped[str] = mapped_column(Text, nullable=False)
    whatsapp_notification_queued: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
