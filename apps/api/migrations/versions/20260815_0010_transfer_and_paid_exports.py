# ruff: noqa: E501
"""transactional Website transfer and paid ZIP exports

Revision ID: 20260815_0010
Revises: 20260814_0009
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260815_0010"
down_revision: str | None = "20260814_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ownership_transfers DROP CONSTRAINT ck_ownership_transfers_status;
        ALTER TABLE ownership_transfers ADD COLUMN confirmation_version varchar(40);
        ALTER TABLE ownership_transfers ADD COLUMN validated_at timestamptz;
        ALTER TABLE ownership_transfers ADD CONSTRAINT ck_ownership_transfers_status CHECK (
          status IN ('REQUESTED','VALIDATED','DEACTIVATING','COMPLETED','FAILED','CANCELLED')
        );
        CREATE UNIQUE INDEX uq_ownership_transfers_active_website
          ON ownership_transfers(website_id)
          WHERE status IN ('REQUESTED','VALIDATED','DEACTIVATING');

        CREATE TABLE export_prices (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          currency varchar(3) NOT NULL,
          amount_minor bigint NOT NULL,
          active boolean NOT NULL DEFAULT false,
          version integer NOT NULL,
          effective_at timestamptz NOT NULL,
          configured_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_export_prices_amount CHECK (amount_minor > 0),
          CONSTRAINT ck_export_prices_currency CHECK (currency IN ('INR','USD')),
          CONSTRAINT ck_export_prices_version CHECK (version > 0),
          CONSTRAINT uq_export_prices_currency_version UNIQUE(currency, version)
        );
        CREATE UNIQUE INDEX uq_export_prices_active_currency
          ON export_prices(currency) WHERE active;

        CREATE TABLE export_purchases (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE RESTRICT,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          website_version_id uuid NOT NULL REFERENCES website_versions(id) ON DELETE RESTRICT,
          website_version_checksum varchar(80) NOT NULL,
          export_price_id uuid NOT NULL REFERENCES export_prices(id) ON DELETE RESTRICT,
          price_version integer NOT NULL,
          amount_minor bigint NOT NULL,
          currency varchar(3) NOT NULL,
          state varchar(24) NOT NULL DEFAULT 'CREATED',
          idempotency_key varchar(160) NOT NULL,
          paid_at timestamptz,
          generation_requested_at timestamptz,
          ready_at timestamptz,
          expires_at timestamptz,
          failure_code varchar(100),
          safe_error text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_export_purchases_state CHECK (
            state IN ('CREATED','PAYMENT_PENDING','PAID','GENERATING','READY','FAILED','EXPIRED','REFUNDED')
          ),
          CONSTRAINT ck_export_purchases_amount CHECK (amount_minor > 0),
          CONSTRAINT ck_export_purchases_currency CHECK (currency IN ('INR','USD')),
          CONSTRAINT ck_export_purchases_price_version CHECK (price_version > 0),
          CONSTRAINT uq_export_purchases_idempotency UNIQUE(owner_user_id, idempotency_key)
        );
        CREATE INDEX ix_export_purchases_owner_time ON export_purchases(owner_user_id, created_at);
        CREATE INDEX ix_export_purchases_website_state ON export_purchases(website_id, state, created_at);

        ALTER TABLE payments ALTER COLUMN plan_id DROP NOT NULL;
        ALTER TABLE payments ALTER COLUMN price_id DROP NOT NULL;
        ALTER TABLE payments ADD COLUMN export_purchase_id uuid;
        ALTER TABLE payments ADD CONSTRAINT fk_payments_export_purchase
          FOREIGN KEY (export_purchase_id) REFERENCES export_purchases(id) ON DELETE RESTRICT;
        ALTER TABLE payments DROP CONSTRAINT ck_payments_purpose;
        ALTER TABLE payments ADD CONSTRAINT ck_payments_purpose
          CHECK (purpose IN ('SUBSCRIPTION','EXPORT'));
        ALTER TABLE payments ADD CONSTRAINT ck_payments_purpose_reference CHECK (
          (purpose = 'SUBSCRIPTION' AND plan_id IS NOT NULL AND price_id IS NOT NULL AND export_purchase_id IS NULL)
          OR (purpose = 'EXPORT' AND plan_id IS NULL AND price_id IS NULL AND export_purchase_id IS NOT NULL)
        );
        CREATE UNIQUE INDEX uq_payments_export_purchase
          ON payments(export_purchase_id) WHERE export_purchase_id IS NOT NULL;

        CREATE TABLE website_export_artifacts (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          purchase_id uuid NOT NULL REFERENCES export_purchases(id) ON DELETE RESTRICT,
          object_key varchar(1024) NOT NULL,
          checksum_sha256 varchar(64) NOT NULL,
          byte_size bigint NOT NULL,
          manifest jsonb NOT NULL,
          expires_at timestamptz NOT NULL,
          download_count integer NOT NULL DEFAULT 0,
          last_downloaded_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_website_export_artifacts_size CHECK (byte_size > 0),
          CONSTRAINT ck_website_export_artifacts_download_count CHECK (download_count >= 0),
          CONSTRAINT uq_website_export_artifacts_purchase UNIQUE(purchase_id),
          CONSTRAINT uq_website_export_artifacts_object_key UNIQUE(object_key)
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE website_export_artifacts;
        DROP INDEX uq_payments_export_purchase;
        ALTER TABLE payments DROP CONSTRAINT ck_payments_purpose_reference;
        ALTER TABLE payments DROP CONSTRAINT ck_payments_purpose;
        ALTER TABLE payments ADD CONSTRAINT ck_payments_purpose CHECK (purpose = 'SUBSCRIPTION');
        ALTER TABLE payments DROP CONSTRAINT fk_payments_export_purchase;
        ALTER TABLE payments DROP COLUMN export_purchase_id;
        ALTER TABLE payments ALTER COLUMN price_id SET NOT NULL;
        ALTER TABLE payments ALTER COLUMN plan_id SET NOT NULL;
        DROP TABLE export_purchases;
        DROP TABLE export_prices;
        DROP INDEX uq_ownership_transfers_active_website;
        ALTER TABLE ownership_transfers DROP CONSTRAINT ck_ownership_transfers_status;
        ALTER TABLE ownership_transfers DROP COLUMN validated_at;
        ALTER TABLE ownership_transfers DROP COLUMN confirmation_version;
        ALTER TABLE ownership_transfers ADD CONSTRAINT ck_ownership_transfers_status
          CHECK (status IN ('COMPLETED','FAILED'));
        """
    )