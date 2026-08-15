"""activation, attribution, retention, and website value analytics

Revision ID: 20260823_0018
Revises: 20260822_0017
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260823_0018"
down_revision = "20260822_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "oauth_transactions",
        sa.Column("attribution", postgresql.JSONB(), server_default="{}", nullable=False),
    )
    op.add_column(
        "oauth_transactions",
        sa.Column("country_code", sa.String(length=2), server_default="ZZ", nullable=False),
    )
    op.create_table(
        "product_events",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("website_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("properties", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_product_events_idempotency"),
    )
    op.create_index("ix_product_events_type_time", "product_events", ["event_type", "occurred_at"])
    op.create_index("ix_product_events_user_time", "product_events", ["user_id", "occurred_at"])
    op.create_index(
        "ix_product_events_website_time", "product_events", ["website_id", "occurred_at"]
    )

    op.create_table(
        "website_value_states",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("website_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_visitor_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_lead_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("website_id", name="uq_website_value_states_website"),
    )
    op.create_index(
        "ix_website_value_states_owner", "website_value_states", ["owner_user_id", "published_at"]
    )
    op.create_index("ix_website_value_states_first_lead", "website_value_states", ["first_lead_at"])

    op.create_table(
        "acquisition_attributions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("normalized_source", sa.String(length=32), nullable=False),
        sa.Column("signup_source", sa.String(length=24), nullable=False),
        sa.Column("country_code", sa.String(length=2), server_default="ZZ", nullable=False),
        sa.Column("utm_source", sa.String(length=160), nullable=True),
        sa.Column("utm_medium", sa.String(length=160), nullable=True),
        sa.Column("utm_campaign", sa.String(length=200), nullable=True),
        sa.Column("utm_content", sa.String(length=200), nullable=True),
        sa.Column("utm_term", sa.String(length=200), nullable=True),
        sa.Column("referrer", sa.String(length=1000), nullable=True),
        sa.Column("landing_page", sa.String(length=1000), nullable=True),
        sa.Column(
            "captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_acquisition_attributions_user"),
    )
    op.create_index(
        "ix_acquisition_attributions_source_time",
        "acquisition_attributions",
        ["normalized_source", "captured_at"],
    )
    op.create_index(
        "ix_acquisition_attributions_country_time",
        "acquisition_attributions",
        ["country_code", "captured_at"],
    )

    op.create_table(
        "website_digest_deliveries",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("website_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("digest_month", sa.String(length=7), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("transactional_email_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("safe_error_code", sa.String(length=100), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("channel IN ('EMAIL','WHATSAPP')", name="ck_digest_deliveries_channel"),
        sa.CheckConstraint(
            "state IN ('PENDING','SENT','FAILED','SKIPPED')", name="ck_digest_deliveries_state"
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["transactional_email_id"], ["transactional_emails.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "website_id", "digest_month", "channel", name="uq_digest_deliveries_period"
        ),
    )
    op.create_index(
        "ix_digest_deliveries_dispatch", "website_digest_deliveries", ["state", "created_at"]
    )
    op.create_index(
        "ix_digest_deliveries_owner", "website_digest_deliveries", ["owner_user_id", "digest_month"]
    )

    op.create_table(
        "zero_lead_checkpoints",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("website_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkpoint_days", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("checkpoint_days IN (14,30)", name="ck_zero_lead_checkpoint_days"),
        sa.CheckConstraint(
            "state IN ('PENDING','NOTIFIED','SKIPPED')", name="ck_zero_lead_checkpoint_state"
        ),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "website_id", "publication_at", "checkpoint_days", name="uq_zero_lead_checkpoint"
        ),
    )
    op.create_index(
        "ix_zero_lead_checkpoint_owner", "zero_lead_checkpoints", ["owner_user_id", "created_at"]
    )

    op.add_column(
        "analytics_daily_rollups",
        sa.Column("lead_form_opens", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "analytics_daily_rollups",
        sa.Column("lead_form_submissions", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.drop_constraint("ck_transactional_emails_kind", "transactional_emails", type_="check")
    op.create_check_constraint(
        "ck_transactional_emails_kind",
        "transactional_emails",
        "kind IN ('AUTH_VERIFICATION','AUTH_PASSWORD_RESET','LEAD_OWNER_ALERT','WEBSITE_PUBLISHED',"
        "'WEBSITE_PUBLISH_FAILED','TRANSFER_COMPLETED','EXPORT_READY','BILLING_STATE','DOMAIN_STATE',"
        "'ADMIN_TRANSACTIONAL','CONTACT_SUBMISSION','MONTHLY_WEBSITE_DIGEST')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_transactional_emails_kind", "transactional_emails", type_="check")
    op.create_check_constraint(
        "ck_transactional_emails_kind",
        "transactional_emails",
        "kind IN ('AUTH_VERIFICATION','AUTH_PASSWORD_RESET','LEAD_OWNER_ALERT','WEBSITE_PUBLISHED',"
        "'WEBSITE_PUBLISH_FAILED','TRANSFER_COMPLETED','EXPORT_READY','BILLING_STATE','DOMAIN_STATE',"
        "'ADMIN_TRANSACTIONAL','CONTACT_SUBMISSION')",
    )
    op.drop_column("analytics_daily_rollups", "lead_form_submissions")
    op.drop_column("analytics_daily_rollups", "lead_form_opens")
    op.drop_index("ix_zero_lead_checkpoint_owner", table_name="zero_lead_checkpoints")
    op.drop_table("zero_lead_checkpoints")
    op.drop_index("ix_digest_deliveries_owner", table_name="website_digest_deliveries")
    op.drop_index("ix_digest_deliveries_dispatch", table_name="website_digest_deliveries")
    op.drop_table("website_digest_deliveries")
    op.drop_index("ix_acquisition_attributions_country_time", table_name="acquisition_attributions")
    op.drop_index("ix_acquisition_attributions_source_time", table_name="acquisition_attributions")
    op.drop_table("acquisition_attributions")
    op.drop_index("ix_website_value_states_first_lead", table_name="website_value_states")
    op.drop_index("ix_website_value_states_owner", table_name="website_value_states")
    op.drop_table("website_value_states")
    op.drop_index("ix_product_events_website_time", table_name="product_events")
    op.drop_index("ix_product_events_user_time", table_name="product_events")
    op.drop_index("ix_product_events_type_time", table_name="product_events")
    op.drop_table("product_events")
    op.drop_column("oauth_transactions", "country_code")
    op.drop_column("oauth_transactions", "attribution")
