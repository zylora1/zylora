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
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from zylora_api.db.activation_models import (
    AcquisitionAttribution,
    ProductEvent,
    WebsiteDigestDelivery,
    WebsiteValueState,
    ZeroLeadCheckpoint,
)
from zylora_api.db.ai_builder_models import (
    AiGenerationArtifact,
    AiGenerationEvent,
    AiGenerationJob,
    AiSiteGeneration,
    AiSiteProject,
)
from zylora_api.db.auth_models import (
    AuditLog,
    AuthAttempt,
    AuthIdentity,
    EmailVerification,
    OAuthTransaction,
    PasswordReset,
    Session,
    SuperAdminProfile,
    User,
)
from zylora_api.db.base import Base
from zylora_api.db.blog_models import (
    BlogCategory,
    BlogPost,
    BlogPostVersion,
    BlogTag,
)
from zylora_api.db.campaign_models import (
    Campaign,
    CampaignDeliveryEvent,
    CampaignRecipient,
    EmailSuppression,
)
from zylora_api.db.chatbot_models import (
    Chatbot,
    ChatbotKnowledgeChunk,
    ChatbotKnowledgeIndex,
    ChatConversation,
    ChatMessage,
)
from zylora_api.db.commerce_models import (
    ExportPrice,
    ExportPurchase,
    Invoice,
    NotificationQuotaAccount,
    NotificationQuotaLedger,
    Payment,
    PaymentEvent,
    Plan,
    PlanCatalog,
    PlanEntitlement,
    PlanPrice,
    Subscription,
    WebsiteExportArtifact,
)
from zylora_api.db.deployment_models import Deployment, DeploymentEvent, Domain
from zylora_api.db.knowledge_models import KnowledgeSource
from zylora_api.db.lead_models import (
    AnalyticsDailyRollup,
    AnalyticsEvent,
    Lead,
    LeadCreditAccount,
    LeadCreditLedger,
    Notification,
    ProLead,
    TransactionalEmail,
)
from zylora_api.db.template_models import (
    Template,
    TemplateAsset,
    TemplateCategory,
    TemplateTag,
    TemplateTagAssignment,
    TemplateValidation,
    TemplateVersion,
)
from zylora_api.db.website_models import (
    AiCreditAccount,
    AiCreditLedger,
    AiOperation,
    OwnershipTransfer,
    Website,
    WebsiteOwnership,
    WebsitePage,
    WebsitePagePathChange,
    WebsiteVersion,
)
from zylora_api.db.whatsapp_models import (
    WhatsAppCallbackEvent,
    WhatsAppNotification,
    WhatsAppNotificationSetting,
)

__all__ = [
    "AcquisitionAttribution",
    "AiCreditAccount",
    "AiCreditLedger",
    "AiGenerationArtifact",
    "AiGenerationEvent",
    "AiGenerationJob",
    "AiOperation",
    "AiSiteGeneration",
    "AiSiteProject",
    "AnalyticsDailyRollup",
    "AnalyticsEvent",
    "AuditLog",
    "AuthAttempt",
    "AuthIdentity",
    "BlogCategory",
    "BlogPost",
    "BlogPostVersion",
    "BlogTag",
    "Campaign",
    "CampaignDeliveryEvent",
    "CampaignRecipient",
    "ChatConversation",
    "ChatMessage",
    "Chatbot",
    "ChatbotKnowledgeChunk",
    "ChatbotKnowledgeIndex",
    "Deployment",
    "DeploymentEvent",
    "Domain",
    "EmailSuppression",
    "EmailVerification",
    "ExportPrice",
    "ExportPurchase",
    "Invoice",
    "KnowledgeSource",
    "Lead",
    "LeadCreditAccount",
    "LeadCreditLedger",
    "Notification",
    "NotificationQuotaAccount",
    "NotificationQuotaLedger",
    "OAuthTransaction",
    "OwnershipTransfer",
    "PasswordReset",
    "Payment",
    "PaymentEvent",
    "Plan",
    "PlanCatalog",
    "PlanEntitlement",
    "PlanPrice",
    "ProLead",
    "ProductEvent",
    "Session",
    "Subscription",
    "SuperAdminProfile",
    "Template",
    "TemplateAsset",
    "TemplateCategory",
    "TemplateTag",
    "TemplateTagAssignment",
    "TemplateValidation",
    "TemplateVersion",
    "TransactionalEmail",
    "User",
    "Website",
    "WebsiteDigestDelivery",
    "WebsiteExportArtifact",
    "WebsiteOwnership",
    "WebsitePage",
    "WebsitePagePathChange",
    "WebsiteValueState",
    "WebsiteVersion",
    "WhatsAppCallbackEvent",
    "WhatsAppNotification",
    "WhatsAppNotificationSetting",
    "ZeroLeadCheckpoint",
]


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint("state IN ('PENDING','PUBLISHED','FAILED')", name="ck_outbox_events_state"),
        Index("ix_outbox_events_dispatch", "state", "available_at", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    aggregate_type: Mapped[str] = mapped_column(String(80))
    aggregate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(160))
    event_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_owner: Mapped[str | None] = mapped_column(String(160))
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    correlation_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','DEAD_LETTER','CANCELLED')",
            name="ck_job_runs_state",
        ),
        Index("ix_job_runs_operations", "state", "queue", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    outbox_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("outbox_events.id", ondelete="RESTRICT"), unique=True
    )
    task_name: Mapped[str] = mapped_column(String(160))
    queue: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    state: Mapped[str] = mapped_column(String(24), default="PENDING", server_default="PENDING")
    attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(100))
    safe_error_detail: Mapped[str | None] = mapped_column(Text)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlatformMetadata(Base):
    __tablename__ = "platform_metadata"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
