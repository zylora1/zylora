"""domains, immutable deployment attempts, and deployment evidence

Revision ID: 20260814_0009
Revises: 20260813_0008
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260814_0009"
down_revision: str | None = "20260813_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE domains (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE RESTRICT,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          type varchar(24) NOT NULL,
          hostname varchar(253) NOT NULL,
          display_hostname varchar(253) NOT NULL,
          state varchar(32) NOT NULL DEFAULT 'RESERVED',
          verification_record_name varchar(253),
          verification_record_type varchar(12),
          verification_record_value text,
          provider_hostname_id varchar(120) UNIQUE,
          provider_reference varchar(253),
          tls_status varchar(20) NOT NULL DEFAULT 'PENDING',
          is_primary boolean NOT NULL DEFAULT false,
          is_active boolean NOT NULL DEFAULT false,
          last_checked_at timestamptz,
          failure_code varchar(100),
          safe_error text,
          version integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_domains_type CHECK (type IN ('ZYLORA_SUBDOMAIN','CUSTOM')),
          CONSTRAINT ck_domains_state CHECK (state IN ('RESERVED','PENDING_DNS','VERIFIED',
            'VERIFICATION_FAILED','PROVISIONING','ACTIVE','DEGRADED','DEACTIVATING','INACTIVE',
            'PROVISIONING_FAILED')),
          CONSTRAINT ck_domains_tls_status CHECK (tls_status IN ('PENDING','ACTIVE','FAILED','UNKNOWN')),
          CONSTRAINT ck_domains_active_state CHECK (NOT is_active OR state IN ('ACTIVE','DEGRADED')),
          CONSTRAINT uq_domains_hostname UNIQUE(hostname)
        );
        CREATE INDEX ix_domains_website_state ON domains(website_id, state, updated_at);
        CREATE UNIQUE INDEX uq_domains_primary_live_website ON domains(website_id)
          WHERE is_primary AND state IN ('PROVISIONING','ACTIVE','DEGRADED');

        CREATE TABLE deployments (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE RESTRICT,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          website_version_id uuid NOT NULL REFERENCES website_versions(id) ON DELETE RESTRICT,
          domain_id uuid NOT NULL REFERENCES domains(id) ON DELETE RESTRICT,
          previous_deployment_id uuid REFERENCES deployments(id) ON DELETE RESTRICT,
          operation varchar(20) NOT NULL DEFAULT 'PUBLISH',
          state varchar(32) NOT NULL DEFAULT 'QUEUED',
          idempotency_key varchar(160) NOT NULL,
          artifact_key varchar(1024),
          artifact_checksum varchar(64),
          provider_route_reference varchar(253),
          failure_code varchar(100),
          safe_error text,
          queued_at timestamptz NOT NULL DEFAULT now(),
          started_at timestamptz,
          health_checked_at timestamptz,
          switched_at timestamptz,
          completed_at timestamptz,
          CONSTRAINT ck_deployments_operation CHECK (operation IN ('PUBLISH','ROLLBACK')),
          CONSTRAINT ck_deployments_state CHECK (state IN ('QUEUED','VALIDATING','BUILDING',
            'PROVISIONING','HEALTH_CHECKING','SWITCHING','ACTIVE','SUPERSEDED','ROLLING_BACK',
            'FAILED','CANCELLED')),
          CONSTRAINT uq_deployments_website_idempotency UNIQUE(website_id, idempotency_key)
        );
        CREATE INDEX ix_deployments_website_queued ON deployments(website_id, queued_at);
        CREATE UNIQUE INDEX uq_deployments_active_attempt ON deployments(website_id)
          WHERE state IN ('QUEUED','VALIDATING','BUILDING','PROVISIONING','HEALTH_CHECKING',
            'SWITCHING','ROLLING_BACK');

        ALTER TABLE websites ADD COLUMN active_deployment_id uuid;
        ALTER TABLE websites ADD CONSTRAINT fk_websites_active_deployment
          FOREIGN KEY (active_deployment_id) REFERENCES deployments(id) ON DELETE RESTRICT;

        CREATE TABLE deployment_events (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          deployment_id uuid NOT NULL REFERENCES deployments(id) ON DELETE RESTRICT,
          from_state varchar(32),
          to_state varchar(32) NOT NULL,
          actor_type varchar(32) NOT NULL,
          actor_id varchar(160),
          correlation_id varchar(128) NOT NULL,
          evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_deployment_events_to_state CHECK (to_state <> '')
        );
        CREATE INDEX ix_deployment_events_deployment_time
          ON deployment_events(deployment_id, created_at);
        CREATE OR REPLACE FUNCTION zylora_deployment_events_immutable() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'deployment events are immutable';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_deployment_events_immutable BEFORE UPDATE OR DELETE ON deployment_events
          FOR EACH ROW EXECUTE FUNCTION zylora_deployment_events_immutable();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_deployment_events_immutable ON deployment_events;
        DROP FUNCTION IF EXISTS zylora_deployment_events_immutable();
        DROP TABLE deployment_events;
        ALTER TABLE websites DROP CONSTRAINT fk_websites_active_deployment;
        ALTER TABLE websites DROP COLUMN active_deployment_id;
        DROP TABLE deployments;
        DROP TABLE domains;
        """
    )
