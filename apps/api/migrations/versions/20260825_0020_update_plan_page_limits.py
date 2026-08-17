"""update plan page limits to canonical Free=2, Starter=5, Growth=8

Revision ID: 20260825_0020
Revises: 20260824_0019
"""

from alembic import op

revision = "20260825_0020"
down_revision = "20260824_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update max_pages for FREE to 2
    op.execute(
        """
        UPDATE plan_entitlements
        SET value_int = 2
        FROM plans
        WHERE plan_entitlements.plan_id = plans.id
          AND plans.code = 'FREE'
          AND plan_entitlements.capability_key = 'max_pages';
        """
    )
    # Update max_pages for BASIC/STARTER to 5
    op.execute(
        """
        UPDATE plan_entitlements
        SET value_int = 5
        FROM plans
        WHERE plan_entitlements.plan_id = plans.id
          AND plans.code = 'BASIC'
          AND plan_entitlements.capability_key = 'max_pages';
        """
    )
    # Update max_pages for GROWTH to 8
    op.execute(
        """
        UPDATE plan_entitlements
        SET value_int = 8
        FROM plans
        WHERE plan_entitlements.plan_id = plans.id
          AND plans.code = 'GROWTH'
          AND plan_entitlements.capability_key = 'max_pages';
        """
    )
    op.drop_constraint("ck_transactional_emails_kind", "transactional_emails", type_="check")
    op.create_check_constraint(
        "ck_transactional_emails_kind",
        "transactional_emails",
        "kind IN ('AUTH_VERIFICATION','AUTH_PASSWORD_RESET','LEAD_OWNER_ALERT','WEBSITE_PUBLISHED',"
        "'WEBSITE_PUBLISH_FAILED','TRANSFER_COMPLETED','EXPORT_READY','BILLING_STATE','DOMAIN_STATE',"
        "'ADMIN_TRANSACTIONAL','CONTACT_SUBMISSION','MONTHLY_WEBSITE_DIGEST','PRO_PROSPECT_CONFIRMATION')",
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE plan_entitlements
        SET value_int = 1
        FROM plans
        WHERE plan_entitlements.plan_id = plans.id
          AND plans.code = 'FREE'
          AND plan_entitlements.capability_key = 'max_pages';
        """
    )
    op.execute(
        """
        UPDATE plan_entitlements
        SET value_int = 20
        FROM plans
        WHERE plan_entitlements.plan_id = plans.id
          AND plans.code = 'GROWTH'
          AND plan_entitlements.capability_key = 'max_pages';
        """
    )
    op.drop_constraint("ck_transactional_emails_kind", "transactional_emails", type_="check")
    op.create_check_constraint(
        "ck_transactional_emails_kind",
        "transactional_emails",
        "kind IN ('AUTH_VERIFICATION','AUTH_PASSWORD_RESET','LEAD_OWNER_ALERT','WEBSITE_PUBLISHED',"
        "'WEBSITE_PUBLISH_FAILED','TRANSFER_COMPLETED','EXPORT_READY','BILLING_STATE','DOMAIN_STATE',"
        "'ADMIN_TRANSACTIONAL','CONTACT_SUBMISSION','MONTHLY_WEBSITE_DIGEST')",
    )
