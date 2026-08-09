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


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("account_type IN ('USER','SUPER_ADMIN')", name="ck_users_account_type"),
        CheckConstraint(
            "status IN ('PENDING_VERIFICATION','ACTIVE','LOCKED','DELETION_PENDING','DELETED')",
            name="ck_users_status",
        ),
        CheckConstraint(
            "status <> 'ACTIVE' OR verified_at IS NOT NULL", name="ck_users_active_verified"
        ),
        Index(
            "uq_users_one_super_admin",
            text("(account_type = 'SUPER_ADMIN')"),
            unique=True,
            postgresql_where=text("account_type = 'SUPER_ADMIN'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    account_type: Mapped[str] = mapped_column(String(20), default="USER", server_default="USER")
    normalized_email: Mapped[str] = mapped_column(String(320), unique=True)
    display_email: Mapped[str] = mapped_column(String(320))
    password_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING_VERIFICATION", server_default="PENDING_VERIFICATION"
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_epoch: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
    locale: Mapped[str] = mapped_column(String(20), default="en", server_default="en")
    timezone: Mapped[str] = mapped_column(String(80), default="UTC", server_default="UTC")
    version: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SuperAdminProfile(Base):
    __tablename__ = "super_admin_profiles"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthIdentity(Base):
    __tablename__ = "auth_identities"
    __table_args__ = (
        CheckConstraint("provider IN ('PASSWORD','GOOGLE')", name="ck_auth_identities_provider"),
        UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_subject"),
        UniqueConstraint("user_id", "provider", name="uq_auth_identity_user_provider"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20))
    provider_subject: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("audience IN ('USER_WEB','ADMIN_WEB')", name="ck_sessions_audience"),
        Index("ix_sessions_active_user", "user_id", "audience", "revoked_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    csrf_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    audience: Mapped[str] = mapped_column(String(20))
    auth_epoch: Mapped[int] = mapped_column(BigInteger)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    device_name: Mapped[str | None] = mapped_column(String(160))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(100))


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    __table_args__ = (
        CheckConstraint("purpose = 'SIGNUP'", name="ck_email_verifications_purpose"),
        Index(
            "uq_email_verifications_current",
            "user_id",
            "purpose",
            unique=True,
            postgresql_where=text("consumed_at IS NULL AND superseded_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(20), default="SIGNUP", server_default="SIGNUP")
    code_digest: Mapped[bytes] = mapped_column(LargeBinary(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    generation: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordReset(Base):
    __tablename__ = "password_resets"
    __table_args__ = (
        Index(
            "uq_password_resets_current",
            "user_id",
            unique=True,
            postgresql_where=text("consumed_at IS NULL AND superseded_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_digest: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OAuthTransaction(Base):
    __tablename__ = "oauth_transactions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    state_digest: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    nonce_digest: Mapped[bytes] = mapped_column(LargeBinary(32))
    nonce_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    code_verifier_digest: Mapped[bytes] = mapped_column(LargeBinary(32))
    code_verifier_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    redirect_uri: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('SUCCEEDED','FAILED','BLOCKED')",
            name="ck_auth_attempts_outcome",
        ),
        Index("ix_auth_attempts_subject", "action", "subject_digest", "created_at"),
        Index("ix_auth_attempts_ip", "action", "ip_digest", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    action: Mapped[str] = mapped_column(String(60))
    subject_digest: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    ip_digest: Mapped[bytes] = mapped_column(LargeBinary(32))
    outcome: Mapped[str] = mapped_column(String(30))
    reason_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_actor_time", "actor_user_id", "occurred_at"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    event_type: Mapped[str] = mapped_column(String(120))
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(160))
    reason: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str] = mapped_column(String(128))
    ip_digest: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
