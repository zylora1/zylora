"""public contact delivery kind

Revision ID: 20260819_0014
Revises: 20260818_0013
"""

from alembic import op
from sqlalchemy import text

revision = "20260819_0014"
down_revision = "20260818_0013"
branch_labels = None
depends_on = None

KINDS = "'AUTH_VERIFICATION','AUTH_PASSWORD_RESET','LEAD_OWNER_ALERT','WEBSITE_PUBLISHED','WEBSITE_PUBLISH_FAILED','TRANSFER_COMPLETED','EXPORT_READY','BILLING_STATE','DOMAIN_STATE','ADMIN_TRANSACTIONAL'"


def upgrade() -> None:
    op.execute("ALTER TABLE transactional_emails DROP CONSTRAINT ck_transactional_emails_kind")
    op.execute(
        f"ALTER TABLE transactional_emails ADD CONSTRAINT ck_transactional_emails_kind CHECK (kind IN ({KINDS},'CONTACT_SUBMISSION'))"
    )


def downgrade() -> None:
    count = (
        op.get_bind()
        .execute(
            text("SELECT count(*) FROM transactional_emails WHERE kind = 'CONTACT_SUBMISSION'")
        )
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            "Cannot downgrade while persisted contact submissions exist; retain data or migrate it explicitly."
        )
    op.execute("ALTER TABLE transactional_emails DROP CONSTRAINT ck_transactional_emails_kind")
    op.execute(
        f"ALTER TABLE transactional_emails ADD CONSTRAINT ck_transactional_emails_kind CHECK (kind IN ({KINDS}))"
    )
