"""revision-safe editor and metered AI operations

Revision ID: 20260812_0007
Revises: 20260811_0006
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0007"
down_revision: str | None = "20260811_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column("websites", sa.Column("theme", postgresql.JSONB(), nullable=True))
    op.add_column(
        "websites", sa.Column("revision", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("websites", sa.Column("current_version_id", uuid, nullable=True))
    op.execute(
        """
        UPDATE websites AS w
        SET theme = tv.document->'theme'
        FROM template_versions AS tv
        WHERE tv.id = w.source_template_version_id
        """
    )
    op.alter_column("websites", "theme", nullable=False)

    op.create_table(
        "ai_operations",
        sa.Column("id", uuid, nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("website_id", uuid, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("selected_page_id", uuid, nullable=True),
        sa.Column("prompt_digest", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_template_version", sa.String(40), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("result_revision", sa.Integer(), nullable=True),
        sa.Column("cost_credits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("usage", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("operation_summary", sa.String(240), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("safe_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PLANNING','SUCCEEDED','FAILED')", name="ck_ai_operations_status"
        ),
        sa.CheckConstraint("scope IN ('PAGE','WEBSITE')", name="ck_ai_operations_scope"),
        sa.CheckConstraint("cost_credits >= 0", name="ck_ai_operations_cost"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_operations_owner_time", "ai_operations", ["user_id", "created_at"]
    )

    op.create_table(
        "website_versions",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("website_id", uuid, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", uuid, nullable=True),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("page_state", postgresql.JSONB(), nullable=False),
        sa.Column("checksum", sa.String(80), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("operation_id", uuid, nullable=True),
        sa.Column("ai_operation_id", uuid, nullable=True),
        sa.Column("edit_summary", sa.String(240), nullable=False),
        sa.Column("validation_status", sa.String(20), nullable=False),
        sa.Column("validation_results", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source IN ('TEMPLATE','MANUAL','AI','RESTORE','SYSTEM_MIGRATION')",
            name="ck_website_versions_source",
        ),
        sa.CheckConstraint(
            "validation_status IN ('VALID')",
            name="ck_website_versions_validation_status",
        ),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_version_id"], ["website_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ai_operation_id"], ["ai_operations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("website_id", "revision", name="uq_website_versions_revision"),
        sa.UniqueConstraint("website_id", "operation_id", name="uq_website_versions_operation"),
    )
    op.create_index(
        "ix_website_versions_history", "website_versions", ["website_id", "revision"]
    )
    op.create_foreign_key(
        "fk_websites_current_version",
        "websites",
        "website_versions",
        ["current_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "ai_credit_accounts",
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.Column("allowance", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("balance >= 0", name="ck_ai_credit_accounts_balance"),
        sa.CheckConstraint("allowance >= 0", name="ck_ai_credit_accounts_allowance"),
        sa.CheckConstraint("period_end > period_start", name="ck_ai_credit_accounts_period"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "ai_credit_ledger",
        sa.Column("id", uuid, server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("operation_id", uuid, nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(24), nullable=False),
        sa.Column("resulting_balance", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(160), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "entry_type IN ('MONTHLY_GRANT','AI_EDIT','ADJUSTMENT')",
            name="ck_ai_credit_ledger_type",
        ),
        sa.CheckConstraint("resulting_balance >= 0", name="ck_ai_credit_ledger_balance"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "operation_id", name="uq_ai_credit_ledger_operation"),
    )
    op.create_index(
        "ix_ai_credit_ledger_owner_time", "ai_credit_ledger", ["user_id", "created_at"]
    )

    op.execute(
        """
        WITH page_snapshots AS (
          SELECT
            w.id AS website_id,
            w.owner_user_id,
            w.source_template_version_id,
            jsonb_agg(
              jsonb_build_object(
                'id', p.id::text,
                'source_template_page_id', p.source_template_page_id,
                'parent_page_id', CASE WHEN p.parent_page_id IS NULL THEN NULL ELSE p.parent_page_id::text END,
                'name', p.name,
                'slug', p.slug,
                'sort_order', p.sort_order,
                'is_home', p.is_home,
                'show_in_navigation', p.show_in_navigation,
                'status', p.status,
                'content', p.content,
                'seo', p.seo
              ) ORDER BY p.sort_order, p.id
            ) AS page_state,
            jsonb_agg(
              jsonb_build_object(
                'id', 'p' || replace(p.id::text, '-', ''),
                'slug', CASE WHEN p.is_home THEN 'home' ELSE p.slug END,
                'label', p.name,
                'parent_page_id', CASE
                  WHEN p.parent_page_id IS NULL THEN NULL
                  ELSE 'p' || replace(p.parent_page_id::text, '-', '')
                END,
                'sort_order', p.sort_order,
                'is_home', p.is_home,
                'show_in_navigation', p.show_in_navigation,
                'status', CASE WHEN p.status = 'DRAFT' THEN 'ACTIVE' ELSE 'HIDDEN' END,
                'seo', jsonb_build_object(
                  'title', left(coalesce(nullif(p.seo->>'title', ''), p.name), 60),
                  'description', left(coalesce(nullif(p.seo->>'description', ''), 'Information about ' || p.name), 160)
                ),
                'components', CASE
                  WHEN jsonb_array_length(coalesce(p.content->'components', '[]'::jsonb)) > 0
                    THEN p.content->'components'
                  ELSE jsonb_build_array(jsonb_build_object(
                    'id', 'hero-' || left(replace(p.id::text, '-', ''), 12),
                    'type', 'HERO',
                    'props', jsonb_build_object('heading', p.name, 'body', 'Add your page content.'),
                    'children', '[]'::jsonb,
                    'responsive', '{}'::jsonb,
                    'interactions', '[]'::jsonb
                  ))
                END
              ) ORDER BY p.sort_order, p.id
            ) AS document_pages
          FROM websites AS w
          JOIN website_pages AS p ON p.website_id = w.id
          GROUP BY w.id, w.owner_user_id, w.source_template_version_id
        ),
        snapshots AS (
          SELECT
            ps.*,
            jsonb_build_object(
              'schema_version', tv.document->'schema_version',
              'registry_version', tv.document->'registry_version',
              'metadata', tv.document->'metadata',
              'theme', w.theme,
              'assets', coalesce(tv.document->'assets', '[]'::jsonb),
              'pages', ps.document_pages,
              'features', coalesce(tv.document->'features', '[]'::jsonb),
              'requirements', coalesce(tv.document->'requirements', '[]'::jsonb),
              'provenance', tv.document->'provenance'
            ) AS document
          FROM page_snapshots AS ps
          JOIN websites AS w ON w.id = ps.website_id
          JOIN template_versions AS tv ON tv.id = ps.source_template_version_id
        ),
        inserted AS (
          INSERT INTO website_versions (
            website_id, revision, schema_version, document, page_state, checksum, source,
            actor_user_id, edit_summary, validation_status, validation_results
          )
          SELECT
            website_id, 1, coalesce(document->>'schema_version', '1.0.0'), document, page_state,
            md5(document::text) || md5(document::text), 'SYSTEM_MIGRATION', owner_user_id,
            'Phase 6 revision history backfill', 'VALID', '{"backfill": true}'::jsonb
          FROM snapshots
          RETURNING id, website_id
        )
        UPDATE websites AS w
        SET revision = 1, current_version_id = inserted.id
        FROM inserted
        WHERE w.id = inserted.website_id
        """
    )
    op.execute(
        """
        INSERT INTO ai_credit_accounts (
          user_id, balance, allowance, period_start, period_end
        )
        SELECT
          id, 15, 15, date_trunc('month', now()),
          date_trunc('month', now()) + interval '1 month'
        FROM users
        WHERE account_type = 'USER'
        ON CONFLICT (user_id) DO NOTHING;

        INSERT INTO ai_credit_ledger (
          user_id, operation_id, delta, entry_type, resulting_balance, reason
        )
        SELECT user_id, uuidv7(), 15, 'MONTHLY_GRANT', 15, 'Initial Free AI allowance'
        FROM ai_credit_accounts
        WHERE NOT EXISTS (
          SELECT 1 FROM ai_credit_ledger AS l WHERE l.user_id = ai_credit_accounts.user_id
        );
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_website_version_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'website_versions are immutable';
        END;
        $$;
        CREATE TRIGGER trg_website_versions_immutable
        BEFORE UPDATE ON website_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_website_version_change();

        CREATE FUNCTION prevent_ai_credit_ledger_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'ai_credit_ledger is immutable';
        END;
        $$;
        CREATE TRIGGER trg_ai_credit_ledger_immutable
        BEFORE UPDATE OR DELETE ON ai_credit_ledger
        FOR EACH ROW EXECUTE FUNCTION prevent_ai_credit_ledger_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ai_credit_ledger_immutable ON ai_credit_ledger")
    op.execute("DROP FUNCTION IF EXISTS prevent_ai_credit_ledger_change()")
    op.execute("DROP TRIGGER IF EXISTS trg_website_versions_immutable ON website_versions")
    op.execute("DROP FUNCTION IF EXISTS prevent_website_version_change()")
    op.drop_index("ix_ai_credit_ledger_owner_time", table_name="ai_credit_ledger")
    op.drop_table("ai_credit_ledger")
    op.drop_table("ai_credit_accounts")
    op.drop_constraint("fk_websites_current_version", "websites", type_="foreignkey")
    op.drop_index("ix_website_versions_history", table_name="website_versions")
    op.drop_table("website_versions")
    op.drop_index("ix_ai_operations_owner_time", table_name="ai_operations")
    op.drop_table("ai_operations")
    op.drop_column("websites", "current_version_id")
    op.drop_column("websites", "revision")
    op.drop_column("websites", "theme")
