"""knowledge documents and Twilio WhatsApp lead notifications

Revision ID: 20260822_0017
Revises: 20260821_0016
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260822_0017"
down_revision = "20260821_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("website_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("safe_display_name", sa.String(length=240), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("extracted_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("mime_type", sa.String(length=160), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="UPLOADED", nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message_safe", sa.String(length=500), nullable=True),
        sa.Column("extraction_metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_type IN ('WEBSITE','PDF','DOCX','TEXT','MARKDOWN')",
            name="ck_knowledge_sources_type",
        ),
        sa.CheckConstraint(
            "status IN ('UPLOADED','SCANNING','PROCESSING','READY','FAILED','DELETED')",
            name="ck_knowledge_sources_status",
        ),
        sa.CheckConstraint("byte_size >= 0", name="ck_knowledge_sources_size"),
        sa.CheckConstraint("version > 0", name="ck_knowledge_sources_version"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_knowledge_sources_storage_key"),
    )
    op.create_index(
        "ix_knowledge_sources_website_status",
        "knowledge_sources",
        ["website_id", "status", "created_at"],
    )
    op.create_index(
        "ix_knowledge_sources_owner_website", "knowledge_sources", ["owner_user_id", "website_id"]
    )

    op.drop_constraint(
        "uq_chatbot_index_website_version", "chatbot_knowledge_indexes", type_="unique"
    )
    op.add_column(
        "chatbot_knowledge_indexes",
        sa.Column("knowledge_generation", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_unique_constraint(
        "uq_chatbot_index_website_version_generation",
        "chatbot_knowledge_indexes",
        ["website_id", "website_version_id", "knowledge_generation"],
    )
    op.add_column(
        "chatbot_knowledge_chunks",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chatbot_knowledge_chunks",
        sa.Column("source_type", sa.String(length=20), server_default="WEBSITE", nullable=False),
    )
    op.add_column(
        "chatbot_knowledge_chunks",
        sa.Column("source_title", sa.String(length=240), server_default="Website", nullable=False),
    )
    op.add_column(
        "chatbot_knowledge_chunks",
        sa.Column("source_location", postgresql.JSONB(), server_default="{}", nullable=False),
    )
    op.create_foreign_key(
        "fk_chatbot_chunks_source",
        "chatbot_knowledge_chunks",
        "knowledge_sources",
        ["source_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "whatsapp_notification_settings",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("phone_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("phone_last4", sa.String(length=4), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="DISABLED", nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('DISABLED','READY','NEEDS_ATTENTION')", name="ck_whatsapp_settings_status"
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", name="uq_whatsapp_settings_owner"),
        sa.UniqueConstraint("phone_hash", name="uq_whatsapp_settings_phone_hash"),
    )

    op.create_table(
        "whatsapp_notifications",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("website_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("setting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("template_content_sid", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=24), server_default="QUEUED", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("provider_message_sid", sa.String(length=80), nullable=True),
        sa.Column("provider_status", sa.String(length=40), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_detail_safe", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("kind IN ('LEAD_OWNER_ALERT','TEST')", name="ck_whatsapp_kind"),
        sa.CheckConstraint(
            "state IN ('QUEUED','SENDING','RETRY_WAIT','SENT','DELIVERED',"
            "'READ','FAILED','SUPPRESSED')",
            name="ck_whatsapp_state",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["setting_id"], ["whatsapp_notification_settings.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_whatsapp_idempotency"),
        sa.UniqueConstraint("provider_message_sid", name="uq_whatsapp_provider_sid"),
    )
    op.create_index(
        "ix_whatsapp_dispatch", "whatsapp_notifications", ["state", "next_attempt_at", "created_at"]
    )
    op.create_index(
        "ix_whatsapp_owner_created", "whatsapp_notifications", ["owner_user_id", "created_at"]
    )

    op.create_table(
        "whatsapp_callback_events",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_message_sid", sa.String(length=80), nullable=False),
        sa.Column("provider_status", sa.String(length=40), nullable=False),
        sa.Column("event_digest", sa.String(length=64), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False),
        sa.Column("processing_outcome", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["whatsapp_notifications.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_digest", name="uq_whatsapp_callback_digest"),
    )
    op.create_index(
        "ix_whatsapp_callback_message",
        "whatsapp_callback_events",
        ["provider_message_sid", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_whatsapp_callback_message", table_name="whatsapp_callback_events")
    op.drop_table("whatsapp_callback_events")
    op.drop_index("ix_whatsapp_owner_created", table_name="whatsapp_notifications")
    op.drop_index("ix_whatsapp_dispatch", table_name="whatsapp_notifications")
    op.drop_table("whatsapp_notifications")
    op.drop_table("whatsapp_notification_settings")
    op.drop_constraint("fk_chatbot_chunks_source", "chatbot_knowledge_chunks", type_="foreignkey")
    op.drop_column("chatbot_knowledge_chunks", "source_location")
    op.drop_column("chatbot_knowledge_chunks", "source_title")
    op.drop_column("chatbot_knowledge_chunks", "source_type")
    op.drop_column("chatbot_knowledge_chunks", "source_id")
    # The legacy schema permits only one index per Website version. Retain the
    # current active index when present, otherwise the newest generation, and
    # remove dependent chunks before restoring that legacy invariant.
    op.execute(
        """
        WITH ranked AS (
          SELECT indexes.id,
                 row_number() OVER (
                   PARTITION BY indexes.website_id, indexes.website_version_id
                   ORDER BY
                     CASE WHEN indexes.id = chatbots.active_index_id THEN 0 ELSE 1 END,
                     indexes.knowledge_generation DESC,
                     indexes.activated_at DESC NULLS LAST,
                     indexes.created_at DESC,
                     indexes.id DESC
                 ) AS row_number
          FROM chatbot_knowledge_indexes AS indexes
          JOIN chatbots ON chatbots.id = indexes.chatbot_id
        )
        DELETE FROM chatbot_knowledge_chunks AS chunks
        USING ranked
        WHERE chunks.knowledge_index_id = ranked.id
          AND ranked.row_number > 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
          SELECT indexes.id,
                 row_number() OVER (
                   PARTITION BY indexes.website_id, indexes.website_version_id
                   ORDER BY
                     CASE WHEN indexes.id = chatbots.active_index_id THEN 0 ELSE 1 END,
                     indexes.knowledge_generation DESC,
                     indexes.activated_at DESC NULLS LAST,
                     indexes.created_at DESC,
                     indexes.id DESC
                 ) AS row_number
          FROM chatbot_knowledge_indexes AS indexes
          JOIN chatbots ON chatbots.id = indexes.chatbot_id
        )
        DELETE FROM chatbot_knowledge_indexes AS indexes
        USING ranked
        WHERE indexes.id = ranked.id
          AND ranked.row_number > 1
        """
    )
    op.drop_constraint(
        "uq_chatbot_index_website_version_generation",
        "chatbot_knowledge_indexes",
        type_="unique",
    )
    op.drop_column("chatbot_knowledge_indexes", "knowledge_generation")
    op.create_unique_constraint(
        "uq_chatbot_index_website_version",
        "chatbot_knowledge_indexes",
        ["website_id", "website_version_id"],
    )
    op.drop_index("ix_knowledge_sources_owner_website", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_website_status", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
