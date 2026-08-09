"""persist canonical Page path changes for future redirects

Revision ID: 20260811_0006
Revises: 20260810_0005
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0006"
down_revision: str | None = "20260810_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "website_page_path_changes",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("website_id", uuid, nullable=False),
        sa.Column("page_id", uuid, nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("old_path", sa.String(1536), nullable=False),
        sa.Column("new_path", sa.String(1536), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("old_path <> new_path", name="ck_website_page_path_changes_distinct"),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_website_page_path_changes_lookup",
        "website_page_path_changes",
        ["website_id", "old_path", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_website_page_path_changes_lookup", table_name="website_page_path_changes")
    op.drop_table("website_page_path_changes")
