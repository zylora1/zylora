# ruff: noqa: E501
"""analytics rollups, notification lifecycle, and transactional email outbox

Revision ID: 20260817_0012
Revises: 20260816_0011
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260817_0012"
down_revision: str | None = "20260816_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE notifications DROP CONSTRAINT ck_notifications_state;
        UPDATE notifications SET state = 'UNREAD' WHERE state = 'QUEUED';
        ALTER TABLE notifications ADD COLUMN title varchar(180) NOT NULL DEFAULT 'Zylora update';
        ALTER TABLE notifications ADD COLUMN body varchar(500) NOT NULL DEFAULT '';
        ALTER TABLE notifications ADD COLUMN deep_link varchar(500) NOT NULL DEFAULT '/app/notifications';
        ALTER TABLE notifications ADD CONSTRAINT ck_notifications_state
          CHECK (state IN ('UNREAD','READ','ARCHIVED'));
        ALTER TABLE notifications ALTER COLUMN title DROP DEFAULT;
        ALTER TABLE notifications ALTER COLUMN body DROP DEFAULT;
        ALTER TABLE notifications ALTER COLUMN deep_link DROP DEFAULT;
        CREATE INDEX ix_notifications_recipient_state
          ON notifications(recipient_user_id, state, created_at);

        ALTER TABLE analytics_events ADD COLUMN page_path varchar(1024);
        ALTER TABLE analytics_events ADD COLUMN visitor_hash bytea;
        ALTER TABLE analytics_events ADD COLUMN session_hash bytea;
        CREATE INDEX ix_analytics_events_owner_time
          ON analytics_events(owner_user_id, occurred_at);
        CREATE INDEX ix_analytics_events_website_type_time
          ON analytics_events(website_id, event_type, occurred_at);

        CREATE TABLE analytics_daily_rollups (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE RESTRICT,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          timezone varchar(80) NOT NULL,
          bucket_date date NOT NULL,
          event_count bigint NOT NULL DEFAULT 0,
          page_views bigint NOT NULL DEFAULT 0,
          sessions bigint NOT NULL DEFAULT 0,
          visitors bigint NOT NULL DEFAULT 0,
          leads bigint NOT NULL DEFAULT 0,
          form_leads bigint NOT NULL DEFAULT 0,
          chatbot_leads bigint NOT NULL DEFAULT 0,
          chatbot_conversations bigint NOT NULL DEFAULT 0,
          chatbot_messages bigint NOT NULL DEFAULT 0,
          conversions bigint NOT NULL DEFAULT 0,
          refreshed_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_analytics_daily_rollups_bucket UNIQUE(website_id, timezone, bucket_date)
        );
        CREATE INDEX ix_analytics_daily_rollups_owner_date
          ON analytics_daily_rollups(owner_user_id, bucket_date);

        CREATE TABLE transactional_emails (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          recipient_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
          resource_type varchar(80) NOT NULL,
          resource_id uuid,
          kind varchar(40) NOT NULL,
          recipient_ciphertext bytea NOT NULL,
          content_ciphertext bytea NOT NULL,
          idempotency_key varchar(200) NOT NULL,
          state varchar(20) NOT NULL DEFAULT 'QUEUED',
          attempts integer NOT NULL DEFAULT 0,
          next_attempt_at timestamptz NOT NULL DEFAULT now(),
          provider_message_id varchar(200),
          last_error_code varchar(100),
          sent_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_transactional_emails_kind CHECK (
            kind IN ('AUTH_VERIFICATION','AUTH_PASSWORD_RESET','LEAD_OWNER_ALERT',
                     'WEBSITE_PUBLISHED','WEBSITE_PUBLISH_FAILED','TRANSFER_COMPLETED',
                     'EXPORT_READY','BILLING_STATE','DOMAIN_STATE','ADMIN_TRANSACTIONAL')
          ),
          CONSTRAINT ck_transactional_emails_state CHECK (
            state IN ('QUEUED','SENDING','RETRY_WAIT','SENT','DELIVERED','FAILED','SUPPRESSED')
          ),
          CONSTRAINT uq_transactional_emails_idempotency UNIQUE(idempotency_key)
        );
        CREATE INDEX ix_transactional_emails_dispatch
          ON transactional_emails(state, next_attempt_at, created_at);
        CREATE INDEX ix_transactional_emails_recipient
          ON transactional_emails(recipient_user_id, created_at);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE transactional_emails;
        DROP TABLE analytics_daily_rollups;
        DROP INDEX ix_analytics_events_website_type_time;
        DROP INDEX ix_analytics_events_owner_time;
        ALTER TABLE analytics_events DROP COLUMN session_hash;
        ALTER TABLE analytics_events DROP COLUMN visitor_hash;
        ALTER TABLE analytics_events DROP COLUMN page_path;
        DROP INDEX ix_notifications_recipient_state;
        ALTER TABLE notifications DROP CONSTRAINT ck_notifications_state;
        UPDATE notifications SET state = 'QUEUED' WHERE state = 'UNREAD';
        ALTER TABLE notifications ADD CONSTRAINT ck_notifications_state
          CHECK (state IN ('QUEUED','READ','ARCHIVED'));
        ALTER TABLE notifications DROP COLUMN deep_link;
        ALTER TABLE notifications DROP COLUMN body;
        ALTER TABLE notifications DROP COLUMN title;
        """
    )
