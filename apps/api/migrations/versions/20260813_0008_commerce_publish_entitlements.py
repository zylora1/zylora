# ruff: noqa: E501
"""permanent regional plans, publish eligibility, ownership, and quotas

Revision ID: 20260813_0008
Revises: 20260812_0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260813_0008"
down_revision: str | None = "20260812_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users ADD COLUMN billing_country_code varchar(2) NOT NULL DEFAULT 'ZZ';
        ALTER TABLE users ADD CONSTRAINT ck_users_billing_country
          CHECK (billing_country_code ~ '^[A-Z]{2}$');

        ALTER TABLE websites DROP CONSTRAINT ck_websites_status;
        ALTER TABLE websites ADD COLUMN live_owner_user_id uuid;
        ALTER TABLE websites ADD COLUMN published_version_id uuid;
        ALTER TABLE websites ADD COLUMN publication_domain_type varchar(24);
        ALTER TABLE websites ADD COLUMN publish_request_idempotency_key varchar(160);
        ALTER TABLE websites ADD CONSTRAINT ck_websites_status CHECK (
          status IN ('DRAFT','PUBLISHING','PUBLISHED','UNPUBLISHING','UNPUBLISHED',
                     'TRANSFER_PENDING','TRANSFERRED','ARCHIVED','FAILED')
        );
        ALTER TABLE websites ADD CONSTRAINT fk_websites_live_owner
          FOREIGN KEY (live_owner_user_id) REFERENCES users(id) ON DELETE RESTRICT;
        ALTER TABLE websites ADD CONSTRAINT fk_websites_published_version
          FOREIGN KEY (published_version_id) REFERENCES website_versions(id) ON DELETE RESTRICT;
        UPDATE websites SET live_owner_user_id = owner_user_id WHERE status = 'PUBLISHED';
        ALTER TABLE websites ADD CONSTRAINT ck_websites_live_owner_state CHECK (
          (status IN ('PUBLISHING','PUBLISHED','UNPUBLISHING') AND live_owner_user_id IS NOT NULL)
          OR (status NOT IN ('PUBLISHING','PUBLISHED','UNPUBLISHING') AND live_owner_user_id IS NULL)
        );
        ALTER TABLE websites ADD CONSTRAINT ck_websites_publication_domain_type CHECK (
          publication_domain_type IS NULL
          OR publication_domain_type IN ('ZYLORA_SUBDOMAIN','CUSTOM')
        );
        CREATE UNIQUE INDEX uq_websites_one_live_owner
          ON websites(live_owner_user_id) WHERE live_owner_user_id IS NOT NULL;

        CREATE TABLE website_ownerships (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          started_at timestamptz NOT NULL DEFAULT now(),
          ended_at timestamptz,
          transfer_id uuid,
          acquisition_reason varchar(32) NOT NULL,
          CONSTRAINT ck_website_ownerships_reason
            CHECK (acquisition_reason IN ('TEMPLATE_CREATION','TRANSFER')),
          CONSTRAINT ck_website_ownerships_time CHECK (ended_at IS NULL OR ended_at >= started_at)
        );
        CREATE UNIQUE INDEX uq_website_ownerships_current
          ON website_ownerships(website_id) WHERE ended_at IS NULL;
        CREATE INDEX ix_website_ownerships_owner_time
          ON website_ownerships(owner_user_id, started_at);
        INSERT INTO website_ownerships
          (id, website_id, owner_user_id, started_at, acquisition_reason)
        SELECT md5(id::text || '-initial-owner')::uuid, id, owner_user_id, created_at,
               'TEMPLATE_CREATION'
        FROM websites;

        CREATE TABLE ownership_transfers (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE RESTRICT,
          sender_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          recipient_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          status varchar(20) NOT NULL,
          idempotency_key varchar(160) NOT NULL,
          failure_code varchar(100),
          created_at timestamptz NOT NULL DEFAULT now(),
          completed_at timestamptz,
          CONSTRAINT ck_ownership_transfers_status CHECK (status IN ('COMPLETED','FAILED')),
          CONSTRAINT ck_ownership_transfers_distinct CHECK (sender_user_id <> recipient_user_id),
          CONSTRAINT uq_ownership_transfers_idempotency UNIQUE(sender_user_id, idempotency_key)
        );
        CREATE INDEX ix_ownership_transfers_website_time
          ON ownership_transfers(website_id, created_at);
        ALTER TABLE website_ownerships ADD CONSTRAINT fk_website_ownerships_transfer
          FOREIGN KEY (transfer_id) REFERENCES ownership_transfers(id) ON DELETE RESTRICT;

        CREATE TABLE plan_catalogs (
          id uuid PRIMARY KEY,
          region varchar(20) NOT NULL,
          currency varchar(3) NOT NULL,
          interval varchar(16) NOT NULL,
          status varchar(20) NOT NULL,
          version integer NOT NULL,
          effective_at timestamptz NOT NULL,
          notes varchar(500) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_plan_catalogs_region CHECK (region IN ('INDIA','INTERNATIONAL')),
          CONSTRAINT ck_plan_catalogs_currency CHECK (currency IN ('INR','USD')),
          CONSTRAINT ck_plan_catalogs_interval CHECK (interval = 'MONTHLY'),
          CONSTRAINT ck_plan_catalogs_status
            CHECK (status IN ('DRAFT','VALIDATED','PUBLISHED','RETIRED','REJECTED')),
          CONSTRAINT uq_plan_catalogs_version UNIQUE(region, interval, version)
        );
        CREATE UNIQUE INDEX uq_plan_catalogs_current
          ON plan_catalogs(region, interval) WHERE status = 'PUBLISHED';

        CREATE TABLE plans (
          id uuid PRIMARY KEY,
          catalog_id uuid NOT NULL REFERENCES plan_catalogs(id) ON DELETE RESTRICT,
          code varchar(20) NOT NULL,
          name varchar(80) NOT NULL,
          description varchar(240) NOT NULL,
          slot integer NOT NULL,
          most_popular boolean NOT NULL DEFAULT false,
          visible boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_plans_code CHECK (code IN ('FREE','BASIC','GROWTH','BUSINESS')),
          CONSTRAINT ck_plans_slot CHECK (slot BETWEEN 1 AND 4),
          CONSTRAINT uq_plans_catalog_code UNIQUE(catalog_id, code),
          CONSTRAINT uq_plans_catalog_slot UNIQUE(catalog_id, slot)
        );

        CREATE TABLE plan_prices (
          id uuid PRIMARY KEY,
          plan_id uuid NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
          amount_minor bigint NOT NULL,
          currency varchar(3) NOT NULL,
          interval varchar(16) NOT NULL,
          active boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_plan_prices_amount CHECK (amount_minor >= 0),
          CONSTRAINT ck_plan_prices_currency CHECK (currency IN ('INR','USD')),
          CONSTRAINT ck_plan_prices_interval CHECK (interval = 'MONTHLY'),
          CONSTRAINT uq_plan_prices_plan_currency UNIQUE(plan_id, currency, interval)
        );

        CREATE TABLE plan_entitlements (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          plan_id uuid NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
          capability_key varchar(80) NOT NULL,
          value_type varchar(16) NOT NULL,
          value_bool boolean,
          value_int integer,
          value_text varchar(80),
          unit varchar(32),
          CONSTRAINT ck_plan_entitlements_type
            CHECK (value_type IN ('BOOLEAN','INTEGER','ENUM','UNLIMITED')),
          CONSTRAINT ck_plan_entitlements_one_value CHECK (
            (value_type = 'BOOLEAN' AND value_bool IS NOT NULL AND value_int IS NULL AND value_text IS NULL)
            OR (value_type = 'INTEGER' AND value_bool IS NULL AND value_int IS NOT NULL AND value_text IS NULL)
            OR (value_type IN ('ENUM','UNLIMITED') AND value_bool IS NULL AND value_int IS NULL AND value_text IS NOT NULL)
          ),
          CONSTRAINT uq_plan_entitlements_capability UNIQUE(plan_id, capability_key)
        );

        CREATE TABLE subscriptions (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          catalog_id uuid NOT NULL REFERENCES plan_catalogs(id) ON DELETE RESTRICT,
          plan_id uuid NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
          price_id uuid NOT NULL REFERENCES plan_prices(id) ON DELETE RESTRICT,
          state varchar(24) NOT NULL,
          plan_code_snapshot varchar(20) NOT NULL,
          entitlements_snapshot jsonb NOT NULL,
          amount_minor bigint NOT NULL,
          currency varchar(3) NOT NULL,
          interval varchar(16) NOT NULL,
          current_period_start timestamptz NOT NULL,
          current_period_end timestamptz NOT NULL,
          cancel_at_period_end boolean NOT NULL DEFAULT false,
          scheduled_plan_id uuid REFERENCES plans(id) ON DELETE RESTRICT,
          scheduled_price_id uuid REFERENCES plan_prices(id) ON DELETE RESTRICT,
          provider_customer_reference varchar(200),
          provider_subscription_reference varchar(200),
          last_trusted_payment_id uuid,
          version bigint NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_subscriptions_state CHECK (
            state IN ('PENDING','AUTHENTICATING','ACTIVE','RENEWAL_PENDING','PAST_DUE',
                      'CANCELLED','EXPIRED','FAILED')
          ),
          CONSTRAINT ck_subscriptions_amount CHECK (amount_minor >= 0),
          CONSTRAINT ck_subscriptions_currency CHECK (currency IN ('INR','USD')),
          CONSTRAINT ck_subscriptions_interval CHECK (interval = 'MONTHLY'),
          CONSTRAINT ck_subscriptions_period CHECK (current_period_end > current_period_start)
        );
        CREATE UNIQUE INDEX uq_subscriptions_current_user ON subscriptions(user_id)
          WHERE state IN ('PENDING','AUTHENTICATING','ACTIVE','RENEWAL_PENDING','PAST_DUE','CANCELLED');

        CREATE TABLE payments (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          plan_id uuid NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
          price_id uuid NOT NULL REFERENCES plan_prices(id) ON DELETE RESTRICT,
          purpose varchar(24) NOT NULL,
          state varchar(24) NOT NULL,
          expected_amount_minor bigint NOT NULL,
          expected_currency varchar(3) NOT NULL,
          provider varchar(40) NOT NULL,
          provider_payment_reference varchar(200) UNIQUE,
          idempotency_key varchar(160) NOT NULL,
          trusted_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_payments_purpose CHECK (purpose = 'SUBSCRIPTION'),
          CONSTRAINT ck_payments_state CHECK (
            state IN ('CREATED','PENDING','PROCESSING','CAPTURED','SETTLED','FAILED','CANCELLED',
                      'REFUND_PENDING','REFUNDED','PARTIALLY_REFUNDED')
          ),
          CONSTRAINT ck_payments_amount CHECK (expected_amount_minor >= 0),
          CONSTRAINT ck_payments_currency CHECK (expected_currency IN ('INR','USD')),
          CONSTRAINT uq_payments_user_idempotency UNIQUE(user_id, idempotency_key)
        );
        ALTER TABLE subscriptions ADD CONSTRAINT fk_subscriptions_last_payment
          FOREIGN KEY (last_trusted_payment_id) REFERENCES payments(id) ON DELETE RESTRICT;

        CREATE TABLE payment_events (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          payment_id uuid NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
          provider varchar(40) NOT NULL,
          provider_event_id varchar(200) NOT NULL,
          event_type varchar(80) NOT NULL,
          raw_body_hash varchar(64) NOT NULL,
          signature_verified boolean NOT NULL,
          processing_outcome varchar(80) NOT NULL,
          evidence jsonb NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_payment_events_provider_event UNIQUE(provider, provider_event_id)
        );
        CREATE INDEX ix_payment_events_payment_time ON payment_events(payment_id, created_at);

        CREATE TABLE invoices (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          number varchar(80) NOT NULL UNIQUE,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          subscription_id uuid NOT NULL REFERENCES subscriptions(id) ON DELETE RESTRICT,
          payment_id uuid NOT NULL UNIQUE REFERENCES payments(id) ON DELETE RESTRICT,
          line_items jsonb NOT NULL,
          total_minor bigint NOT NULL,
          currency varchar(3) NOT NULL,
          state varchar(16) NOT NULL,
          issued_at timestamptz NOT NULL,
          paid_at timestamptz,
          CONSTRAINT ck_invoices_total CHECK (total_minor >= 0),
          CONSTRAINT ck_invoices_currency CHECK (currency IN ('INR','USD')),
          CONSTRAINT ck_invoices_state CHECK (state IN ('ISSUED','PAID','VOID'))
        );

        CREATE TABLE notification_quota_accounts (
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          channel varchar(20) NOT NULL,
          used integer NOT NULL,
          allowance integer NOT NULL,
          period_start timestamptz NOT NULL,
          period_end timestamptz NOT NULL,
          version bigint NOT NULL DEFAULT 1,
          updated_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(user_id, channel),
          CONSTRAINT ck_notification_quota_channel CHECK (channel = 'WHATSAPP'),
          CONSTRAINT ck_notification_quota_usage CHECK (used >= 0 AND allowance >= 0 AND used <= allowance),
          CONSTRAINT ck_notification_quota_period CHECK (period_end > period_start)
        );
        CREATE TABLE notification_quota_ledger (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          channel varchar(20) NOT NULL,
          operation_id uuid NOT NULL,
          delta integer NOT NULL,
          resulting_used integer NOT NULL,
          reason varchar(160) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_notification_quota_ledger_channel CHECK (channel = 'WHATSAPP'),
          CONSTRAINT ck_notification_quota_ledger_delta CHECK (delta = 1),
          CONSTRAINT ck_notification_quota_ledger_result CHECK (resulting_used >= 0),
          CONSTRAINT uq_notification_quota_operation UNIQUE(user_id, channel, operation_id)
        );

        CREATE TABLE leads (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE RESTRICT,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          source varchar(20) NOT NULL,
          idempotency_key varchar(160) NOT NULL,
          request_fingerprint varchar(64) NOT NULL,
          name varchar(160) NOT NULL,
          email varchar(320),
          phone varchar(80),
          enquiry text NOT NULL,
          whatsapp_notification_queued boolean NOT NULL DEFAULT false,
          captured_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_leads_source CHECK (source IN ('FORM','CHATBOT')),
          CONSTRAINT uq_leads_idempotency UNIQUE(website_id, source, idempotency_key)
        );

        INSERT INTO plan_catalogs
          (id, region, currency, interval, status, version, effective_at, notes)
        VALUES
          ('70000000-0000-0000-0000-000000000001', 'INDIA', 'INR', 'MONTHLY',
           'PUBLISHED', 1, '2026-08-01T00:00:00Z', 'Permanent Phase 7 India monthly catalog'),
          ('70000000-0000-0000-0000-000000000002', 'INTERNATIONAL', 'USD', 'MONTHLY',
           'PUBLISHED', 1, '2026-08-01T00:00:00Z', 'Permanent Phase 7 international monthly catalog');

        INSERT INTO plans (id, catalog_id, code, name, description, slot, most_popular) VALUES
          ('71000000-0000-0000-0000-000000000011','70000000-0000-0000-0000-000000000001','FREE','Free','Publish one branded landing page.',1,false),
          ('71000000-0000-0000-0000-000000000012','70000000-0000-0000-0000-000000000001','BASIC','Basic','A focused Website with a custom domain.',2,false),
          ('71000000-0000-0000-0000-000000000013','70000000-0000-0000-0000-000000000001','GROWTH','Growth','Advanced growth, conversion, and AI tools.',3,true),
          ('71000000-0000-0000-0000-000000000014','70000000-0000-0000-0000-000000000001','BUSINESS','Business','Unlimited-page publishing with fair-use safeguards.',4,false),
          ('71000000-0000-0000-0000-000000000021','70000000-0000-0000-0000-000000000002','FREE','Free','Publish one branded landing page.',1,false),
          ('71000000-0000-0000-0000-000000000022','70000000-0000-0000-0000-000000000002','BASIC','Basic','A focused Website with a custom domain.',2,false),
          ('71000000-0000-0000-0000-000000000023','70000000-0000-0000-0000-000000000002','GROWTH','Growth','Advanced growth, conversion, and AI tools.',3,true),
          ('71000000-0000-0000-0000-000000000024','70000000-0000-0000-0000-000000000002','BUSINESS','Business','Unlimited-page publishing with fair-use safeguards.',4,false);

        INSERT INTO plan_prices (id, plan_id, amount_minor, currency, interval) VALUES
          ('72000000-0000-0000-0000-000000000011','71000000-0000-0000-0000-000000000011',0,'INR','MONTHLY'),
          ('72000000-0000-0000-0000-000000000012','71000000-0000-0000-0000-000000000012',39900,'INR','MONTHLY'),
          ('72000000-0000-0000-0000-000000000013','71000000-0000-0000-0000-000000000013',99900,'INR','MONTHLY'),
          ('72000000-0000-0000-0000-000000000014','71000000-0000-0000-0000-000000000014',199900,'INR','MONTHLY'),
          ('72000000-0000-0000-0000-000000000021','71000000-0000-0000-0000-000000000021',0,'USD','MONTHLY'),
          ('72000000-0000-0000-0000-000000000022','71000000-0000-0000-0000-000000000022',900,'USD','MONTHLY'),
          ('72000000-0000-0000-0000-000000000023','71000000-0000-0000-0000-000000000023',1900,'USD','MONTHLY'),
          ('72000000-0000-0000-0000-000000000024','71000000-0000-0000-0000-000000000024',3900,'USD','MONTHLY');

        INSERT INTO plan_entitlements
          (plan_id, capability_key, value_type, value_bool, value_int, value_text, unit)
        SELECT id, item.key, 'BOOLEAN', item.value, NULL, NULL, NULL
        FROM plans CROSS JOIN LATERAL (VALUES
          ('can_publish', true),
          ('zylora_subdomain', true),
          ('custom_domain', code <> 'FREE'),
          ('remove_branding', code <> 'FREE'),
          ('lead_capture_unlimited', true)
        ) item(key, value);

        INSERT INTO plan_entitlements
          (plan_id, capability_key, value_type, value_bool, value_int, value_text, unit)
        SELECT id, 'max_pages', 'INTEGER', NULL,
          CASE code WHEN 'FREE' THEN 1 WHEN 'BASIC' THEN 5 WHEN 'GROWTH' THEN 20 END,
          NULL, 'pages'
        FROM plans WHERE code <> 'BUSINESS';
        INSERT INTO plan_entitlements
          (plan_id, capability_key, value_type, value_bool, value_int, value_text, unit)
        SELECT id, 'max_pages', 'UNLIMITED', NULL, NULL, 'UNLIMITED', 'pages'
        FROM plans WHERE code = 'BUSINESS';

        INSERT INTO plan_entitlements
          (plan_id, capability_key, value_type, value_bool, value_int, value_text, unit)
        SELECT id, 'ai_monthly_credits', 'INTEGER', NULL,
          CASE code WHEN 'FREE' THEN 15 WHEN 'BASIC' THEN 100 WHEN 'GROWTH' THEN 500 ELSE 1500 END,
          NULL, 'credits'
        FROM plans;
        INSERT INTO plan_entitlements
          (plan_id, capability_key, value_type, value_bool, value_int, value_text, unit)
        SELECT id, 'whatsapp_monthly_notifications', 'INTEGER', NULL,
          CASE code WHEN 'FREE' THEN 0 WHEN 'BASIC' THEN 150 WHEN 'GROWTH' THEN 750 ELSE 2000 END,
          NULL, 'notifications'
        FROM plans;
        INSERT INTO plan_entitlements
          (plan_id, capability_key, value_type, value_bool, value_int, value_text, unit)
        SELECT id, 'analytics_tier', 'ENUM', NULL, NULL,
          CASE code WHEN 'FREE' THEN 'BASIC' WHEN 'BASIC' THEN 'STANDARD'
                    WHEN 'GROWTH' THEN 'ADVANCED' ELSE 'ADVANCED_REPORTING' END,
          NULL
        FROM plans;
        INSERT INTO plan_entitlements
          (plan_id, capability_key, value_type, value_bool, value_int, value_text, unit)
        SELECT id, 'seo_tier', 'ENUM', NULL, NULL,
          CASE code WHEN 'FREE' THEN 'AUTOMATIC_BASIC' WHEN 'BASIC' THEN 'FULL_STANDARD'
                    WHEN 'GROWTH' THEN 'ADVANCED_AI' ELSE 'ADVANCED_MONITORING' END,
          NULL
        FROM plans;

        CREATE OR REPLACE FUNCTION zylora_commercial_rows_immutable() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'published commercial snapshots are immutable';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_plan_catalogs_immutable BEFORE UPDATE OR DELETE ON plan_catalogs
          FOR EACH ROW EXECUTE FUNCTION zylora_commercial_rows_immutable();
        CREATE TRIGGER trg_plans_immutable BEFORE UPDATE OR DELETE ON plans
          FOR EACH ROW EXECUTE FUNCTION zylora_commercial_rows_immutable();
        CREATE TRIGGER trg_plan_prices_immutable BEFORE UPDATE OR DELETE ON plan_prices
          FOR EACH ROW EXECUTE FUNCTION zylora_commercial_rows_immutable();
        CREATE TRIGGER trg_plan_entitlements_immutable BEFORE UPDATE OR DELETE ON plan_entitlements
          FOR EACH ROW EXECUTE FUNCTION zylora_commercial_rows_immutable();
        CREATE TRIGGER trg_payment_events_immutable BEFORE UPDATE OR DELETE ON payment_events
          FOR EACH ROW EXECUTE FUNCTION zylora_commercial_rows_immutable();
        CREATE TRIGGER trg_invoices_immutable BEFORE UPDATE OR DELETE ON invoices
          FOR EACH ROW EXECUTE FUNCTION zylora_commercial_rows_immutable();
        CREATE TRIGGER trg_notification_quota_ledger_immutable
          BEFORE UPDATE OR DELETE ON notification_quota_ledger
          FOR EACH ROW EXECUTE FUNCTION zylora_commercial_rows_immutable();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_notification_quota_ledger_immutable ON notification_quota_ledger;
        DROP TRIGGER IF EXISTS trg_invoices_immutable ON invoices;
        DROP TRIGGER IF EXISTS trg_payment_events_immutable ON payment_events;
        DROP TRIGGER IF EXISTS trg_plan_entitlements_immutable ON plan_entitlements;
        DROP TRIGGER IF EXISTS trg_plan_prices_immutable ON plan_prices;
        DROP TRIGGER IF EXISTS trg_plans_immutable ON plans;
        DROP TRIGGER IF EXISTS trg_plan_catalogs_immutable ON plan_catalogs;
        DROP FUNCTION IF EXISTS zylora_commercial_rows_immutable();
        DROP TABLE leads;
        DROP TABLE notification_quota_ledger;
        DROP TABLE notification_quota_accounts;
        DROP TABLE invoices;
        DROP TABLE payment_events;
        ALTER TABLE subscriptions DROP CONSTRAINT fk_subscriptions_last_payment;
        DROP TABLE payments;
        DROP TABLE subscriptions;
        DROP TABLE plan_entitlements;
        DROP TABLE plan_prices;
        DROP TABLE plans;
        DROP TABLE plan_catalogs;
        ALTER TABLE website_ownerships DROP CONSTRAINT fk_website_ownerships_transfer;
        DROP TABLE ownership_transfers;
        DROP TABLE website_ownerships;
        DROP INDEX uq_websites_one_live_owner;
        ALTER TABLE websites DROP CONSTRAINT ck_websites_publication_domain_type;
        ALTER TABLE websites DROP CONSTRAINT ck_websites_live_owner_state;
        ALTER TABLE websites DROP CONSTRAINT fk_websites_published_version;
        ALTER TABLE websites DROP CONSTRAINT fk_websites_live_owner;
        ALTER TABLE websites DROP CONSTRAINT ck_websites_status;
        ALTER TABLE websites DROP COLUMN publish_request_idempotency_key;
        ALTER TABLE websites DROP COLUMN publication_domain_type;
        ALTER TABLE websites DROP COLUMN published_version_id;
        ALTER TABLE websites DROP COLUMN live_owner_user_id;
        ALTER TABLE websites ADD CONSTRAINT ck_websites_status
          CHECK (status IN ('DRAFT','PUBLISHED','TRANSFER_PENDING','ARCHIVED'));
        ALTER TABLE users DROP CONSTRAINT ck_users_billing_country;
        ALTER TABLE users DROP COLUMN billing_country_code;
        """
    )
