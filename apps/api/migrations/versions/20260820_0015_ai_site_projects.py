"""isolated AI site project handoff

Revision ID: 20260820_0015
Revises: 20260819_0014
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260820_0015"
down_revision = "20260819_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_site_projects",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("prompt_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="QUEUED", nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("builder_build_id", sa.String(length=160), nullable=True),
        sa.Column("artifact_digest", sa.String(length=128), nullable=True),
        sa.Column("safe_error_code", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED','SUBMITTED','PLANNING','GENERATING','VALIDATING',"
            "'READY','FAILED','CANCELLED')",
            name="ck_ai_site_projects_status",
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("builder_build_id"),
        sa.UniqueConstraint(
            "owner_user_id", "idempotency_key", name="uq_ai_site_projects_owner_key"
        ),
    )
    op.create_index(
        "ix_ai_site_projects_owner_updated",
        "ai_site_projects",
        ["owner_user_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_site_projects_owner_updated", table_name="ai_site_projects")
    op.drop_table("ai_site_projects")
