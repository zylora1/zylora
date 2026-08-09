"""authentication and authorization foundation

Revision ID: 20260809_0002
Revises: 20260808_0001
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_0002"
down_revision: str | None = "20260808_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("account_type", sa.String(20), server_default="USER", nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=False),
        sa.Column("display_email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="PENDING_VERIFICATION", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auth_epoch", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("locale", sa.String(20), server_default="en", nullable=False),
        sa.Column("timezone", sa.String(80), server_default="UTC", nullable=False),
        sa.Column("version", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("account_type IN ('USER','SUPER_ADMIN')", name="ck_users_account_type"),
        sa.CheckConstraint(
            "status IN ('PENDING_VERIFICATION','ACTIVE','LOCKED','DELETION_PENDING','DELETED')",
            name="ck_users_status",
        ),
        sa.CheckConstraint("status <> 'ACTIVE' OR verified_at IS NOT NULL", name="ck_users_active_verified"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_email"),
    )
    op.create_index(
        "uq_users_one_super_admin",
        "users",
        [sa.text("(account_type = 'SUPER_ADMIN')")],
        unique=True,
        postgresql_where=sa.text("account_type = 'SUPER_ADMIN'"),
    )

    op.create_table(
        "super_admin_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.execute(
        """
        CREATE FUNCTION enforce_super_admin_profile() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM users WHERE id = NEW.user_id AND account_type = 'SUPER_ADMIN'
          ) THEN
            RAISE EXCEPTION 'super_admin_profiles requires a SUPER_ADMIN user';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE CONSTRAINT TRIGGER trg_super_admin_profile_type
        AFTER INSERT OR UPDATE ON super_admin_profiles
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_super_admin_profile();
        """
    )

    op.create_table(
        "auth_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('PASSWORD','GOOGLE')", name="ck_auth_identities_provider"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_auth_identity_user_provider"),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("csrf_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("auth_epoch", sa.BigInteger(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("device_name", sa.String(160), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(100), nullable=True),
        sa.CheckConstraint("audience IN ('USER_WEB','ADMIN_WEB')", name="ck_sessions_audience"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_index("ix_sessions_active_user", "sessions", ["user_id", "audience", "revoked_at", "expires_at"])

    op.create_table(
        "email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(20), server_default="SIGNUP", nullable=False),
        sa.Column("code_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("generation", sa.Integer(), server_default="1", nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("purpose = 'SIGNUP'", name="ck_email_verifications_purpose"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_verifications_user_id", "email_verifications", ["user_id"])
    op.create_index(
        "uq_email_verifications_current",
        "email_verifications",
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL AND superseded_at IS NULL"),
    )

    op.create_table(
        "password_resets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])
    op.create_index(
        "uq_password_resets_current",
        "password_resets",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL AND superseded_at IS NULL"),
    )

    op.create_table(
        "oauth_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("state_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("nonce_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("nonce_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("code_verifier_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("code_verifier_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("redirect_uri", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_digest"),
    )

    op.create_table(
        "auth_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("subject_digest", sa.LargeBinary(32), nullable=True),
        sa.Column("ip_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("outcome IN ('SUCCEEDED','FAILED','BLOCKED')", name="ck_auth_attempts_outcome"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_attempts_subject", "auth_attempts", ["action", "subject_digest", "created_at"])
    op.create_index("ix_auth_attempts_ip", "auth_attempts", ["action", "ip_digest", "created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_type", sa.String(80), nullable=True),
        sa.Column("target_id", sa.String(160), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("ip_digest", sa.LargeBinary(32), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_time", "audit_logs", ["actor_user_id", "occurred_at"])
    op.execute(
        """
        CREATE FUNCTION reject_audit_log_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_logs are immutable';
        END;
        $$;
        CREATE TRIGGER trg_audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation()")
    op.drop_index("ix_audit_logs_actor_time", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_auth_attempts_ip", table_name="auth_attempts")
    op.drop_index("ix_auth_attempts_subject", table_name="auth_attempts")
    op.drop_table("auth_attempts")
    op.drop_table("oauth_transactions")
    op.drop_index("uq_password_resets_current", table_name="password_resets")
    op.drop_index("ix_password_resets_user_id", table_name="password_resets")
    op.drop_table("password_resets")
    op.drop_index("uq_email_verifications_current", table_name="email_verifications")
    op.drop_index("ix_email_verifications_user_id", table_name="email_verifications")
    op.drop_table("email_verifications")
    op.drop_index("ix_sessions_active_user", table_name="sessions")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_auth_identities_user_id", table_name="auth_identities")
    op.drop_table("auth_identities")
    op.execute("DROP TRIGGER IF EXISTS trg_super_admin_profile_type ON super_admin_profiles")
    op.execute("DROP FUNCTION IF EXISTS enforce_super_admin_profile()")
    op.drop_table("super_admin_profiles")
    op.drop_index("uq_users_one_super_admin", table_name="users")
    op.drop_table("users")
