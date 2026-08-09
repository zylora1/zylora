"""enforce exactly one home Page for every Website

Revision ID: 20260810_0005
Revises: 20260810_0004
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_0005"
down_revision: str | None = "20260810_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION enforce_website_exactly_one_home() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE target_website_id uuid;
        BEGIN
          target_website_id := COALESCE(NEW.website_id, OLD.website_id);
          IF EXISTS (SELECT 1 FROM websites WHERE id = target_website_id)
             AND (SELECT count(*) FROM website_pages
                  WHERE website_id = target_website_id AND is_home) <> 1 THEN
            RAISE EXCEPTION 'every Website requires exactly one home Page';
          END IF;
          RETURN COALESCE(NEW, OLD);
        END;
        $$;
        CREATE CONSTRAINT TRIGGER trg_website_pages_exactly_one_home
        AFTER INSERT OR UPDATE OR DELETE ON website_pages
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_website_exactly_one_home();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_website_pages_exactly_one_home ON website_pages")
    op.execute("DROP FUNCTION IF EXISTS enforce_website_exactly_one_home()")
