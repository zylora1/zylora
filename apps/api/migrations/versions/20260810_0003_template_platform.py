"""canonical template platform

Revision ID: 20260810_0003
Revises: 20260809_0002
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0003"
down_revision: str | None = "20260809_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "template_categories",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "template_tags",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "templates",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("category_id", uuid, nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("featured_order", sa.Integer(), server_default="1000", nullable=False),
        sa.Column("current_published_version_id", uuid, nullable=True),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','DEPRECATED','RETIRED')", name="ck_templates_status"
        ),
        sa.ForeignKeyConstraint(["category_id"], ["template_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_templates_catalog", "templates", ["status", "featured_order", "name"])
    op.create_table(
        "template_versions",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("template_id", uuid, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("registry_version", sa.String(20), nullable=False),
        sa.Column("validation_summary", postgresql.JSONB(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','VALIDATING','VALIDATED','REJECTED','APPROVED','PUBLISHED','DEPRECATED','RETIRED')",
            name="ck_template_versions_status",
        ),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "version", name="uq_template_versions_number"),
    )
    op.create_index(
        "ix_template_versions_template", "template_versions", ["template_id", "created_at"]
    )
    op.create_foreign_key(
        "fk_templates_current_published_version",
        "templates",
        "template_versions",
        ["current_published_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "template_validations",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("template_version_id", uuid, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("validator_version", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id"], ["template_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_template_validations_version",
        "template_validations",
        ["template_version_id", "created_at"],
    )
    op.create_table(
        "template_assets",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("license", sa.String(160), nullable=False),
        sa.Column("provenance", sa.String(160), nullable=False),
        sa.Column("processing_policy", sa.String(80), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('READY','REJECTED')", name="ck_template_assets_status"),
        sa.CheckConstraint(
            "mime_type IN ('image/png','image/jpeg','image/webp')", name="ck_template_assets_mime"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_table(
        "template_tag_assignments",
        sa.Column("template_id", uuid, nullable=False),
        sa.Column("tag_id", uuid, nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["template_tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("template_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("template_tag_assignments")
    op.drop_table("template_assets")
    op.drop_index("ix_template_validations_version", table_name="template_validations")
    op.drop_table("template_validations")
    op.drop_constraint("fk_templates_current_published_version", "templates", type_="foreignkey")
    op.drop_index("ix_template_versions_template", table_name="template_versions")
    op.drop_table("template_versions")
    op.drop_index("ix_templates_catalog", table_name="templates")
    op.drop_table("templates")
    op.drop_table("template_tags")
    op.drop_table("template_categories")
