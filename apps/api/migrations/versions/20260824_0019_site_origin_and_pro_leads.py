"""add site_origin to websites and create pro_leads table

Revision ID: 20260824_0019
Revises: 20260823_0018
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260824_0019"
down_revision = "20260823_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "websites",
        sa.Column(
            "site_origin",
            sa.String(length=16),
            server_default="TEMPLATE",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_websites_site_origin",
        "websites",
        "site_origin IN ('TEMPLATE','AI')",
    )

    op.create_table(
        "pro_leads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("reference_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("website_type", sa.String(length=150), nullable=False),
        sa.Column("preferred_contact_time", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("amount_received", sa.BigInteger(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("is_spam", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("spam_score", sa.Integer(), nullable=True),
        sa.Column("spam_reason_code", sa.String(length=64), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('PENDING','CLOSED','NOT_CLOSED')",
            name="ck_pro_leads_status",
        ),
        sa.UniqueConstraint("reference_id", name="uq_pro_leads_reference_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_pro_leads_idempotency_key"),
    )
    op.create_index("ix_pro_leads_status_submitted", "pro_leads", ["status", "submitted_at"])
    op.create_index(
        "ix_pro_leads_fingerprint", "pro_leads", ["request_fingerprint", "submitted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_pro_leads_fingerprint", table_name="pro_leads")
    op.drop_index("ix_pro_leads_status_submitted", table_name="pro_leads")
    op.drop_table("pro_leads")
    op.drop_constraint("ck_websites_site_origin", "websites", type_="check")
    op.drop_column("websites", "site_origin")
