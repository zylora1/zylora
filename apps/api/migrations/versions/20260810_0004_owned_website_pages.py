"""owned Website Drafts and hierarchical Pages

Revision ID: 20260810_0004
Revises: 20260810_0003
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0004"
down_revision: str | None = "20260810_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "websites",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("owner_user_id", uuid, nullable=False),
        sa.Column("source_template_version_id", uuid, nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), server_default="DRAFT", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','TRANSFER_PENDING','ARCHIVED')",
            name="ck_websites_status",
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_template_version_id"], ["template_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_websites_owner_status", "websites", ["owner_user_id", "status", "updated_at"]
    )
    op.create_table(
        "website_pages",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("website_id", uuid, nullable=False),
        sa.Column("source_template_page_id", sa.String(64), nullable=False),
        sa.Column("parent_page_id", uuid, nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_home", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("show_in_navigation", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("seo", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','HIDDEN','ARCHIVED')", name="ck_website_pages_status"
        ),
        sa.CheckConstraint(
            "parent_page_id IS NULL OR parent_page_id <> id",
            name="ck_website_pages_not_self_parent",
        ),
        sa.CheckConstraint(
            "(is_home AND parent_page_id IS NULL AND slug = '') OR (NOT is_home AND slug <> '')",
            name="ck_website_pages_home_shape",
        ),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "website_id", name="uq_website_pages_id_website"),
    )
    op.create_foreign_key(
        "fk_website_pages_parent_same_website",
        "website_pages",
        "website_pages",
        ["parent_page_id", "website_id"],
        ["id", "website_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_website_pages_navigation",
        "website_pages",
        ["website_id", "parent_page_id", "sort_order"],
    )
    op.create_index(
        "uq_website_pages_one_home",
        "website_pages",
        ["website_id"],
        unique=True,
        postgresql_where=sa.text("is_home"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_website_pages_sibling_slug ON website_pages (website_id, coalesce(parent_page_id, '00000000-0000-0000-0000-000000000000'::uuid), slug)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_website_pages_sibling_slug")
    op.drop_index("uq_website_pages_one_home", table_name="website_pages")
    op.drop_index("ix_website_pages_navigation", table_name="website_pages")
    op.drop_constraint("fk_website_pages_parent_same_website", "website_pages", type_="foreignkey")
    op.drop_table("website_pages")
    op.drop_index("ix_websites_owner_status", table_name="websites")
    op.drop_table("websites")
