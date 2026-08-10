# ruff: noqa: E501
"""FAISS chatbot, unified Leads, and append-only lead credits

Revision ID: 20260816_0011
Revises: 20260815_0010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260816_0011"
down_revision: str | None = "20260815_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE leads ADD COLUMN source_reference_id uuid;
        ALTER TABLE leads ADD COLUMN page_path varchar(1024);
        ALTER TABLE leads ADD COLUMN consent jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE leads ADD COLUMN status varchar(20) NOT NULL DEFAULT 'NEW';
        ALTER TABLE leads ADD COLUMN retention_until timestamptz;
        ALTER TABLE leads ADD COLUMN version integer NOT NULL DEFAULT 1;
        ALTER TABLE leads ADD CONSTRAINT ck_leads_status
          CHECK (status IN ('NEW','CONTACTED','QUALIFIED','ARCHIVED'));
        CREATE INDEX ix_leads_owner_captured ON leads(owner_user_id, captured_at);
        CREATE INDEX ix_leads_website_source ON leads(website_id, source, captured_at);

        CREATE TABLE lead_credit_accounts (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          user_id uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
          balance bigint NOT NULL DEFAULT 0,
          version integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_lead_credit_accounts_version CHECK (version > 0)
        );

        CREATE TABLE lead_credit_ledger (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          lead_id uuid REFERENCES leads(id) ON DELETE RESTRICT,
          actor_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
          entry_type varchar(24) NOT NULL,
          delta bigint NOT NULL,
          resulting_balance bigint NOT NULL,
          idempotency_key varchar(160) NOT NULL,
          reason varchar(240) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_lead_credit_ledger_type CHECK (
            entry_type IN ('PURCHASE','LEAD_CAPTURE','ADMIN_GRANT','REFUND','CORRECTION')
          ),
          CONSTRAINT ck_lead_credit_ledger_delta CHECK (delta <> 0),
          CONSTRAINT ck_lead_credit_ledger_lead_capture CHECK (
            (entry_type <> 'LEAD_CAPTURE') OR (delta = -1 AND lead_id IS NOT NULL)
          ),
          CONSTRAINT uq_lead_credit_ledger_idempotency UNIQUE(user_id, idempotency_key)
        );
        CREATE UNIQUE INDEX uq_lead_credit_ledger_lead
          ON lead_credit_ledger(lead_id) WHERE lead_id IS NOT NULL;
        CREATE INDEX ix_lead_credit_ledger_user_created
          ON lead_credit_ledger(user_id, created_at);
        CREATE FUNCTION forbid_lead_credit_ledger_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'lead_credit_ledger is append-only';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_forbid_lead_credit_ledger_mutation
          BEFORE UPDATE OR DELETE ON lead_credit_ledger
          FOR EACH ROW EXECUTE FUNCTION forbid_lead_credit_ledger_mutation();

        CREATE TABLE notifications (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          recipient_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          type varchar(80) NOT NULL,
          resource_type varchar(80) NOT NULL,
          resource_id uuid NOT NULL,
          data jsonb NOT NULL DEFAULT '{}'::jsonb,
          dedupe_key varchar(200) NOT NULL,
          state varchar(20) NOT NULL DEFAULT 'QUEUED',
          read_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_notifications_state CHECK (state IN ('QUEUED','READ','ARCHIVED')),
          CONSTRAINT uq_notifications_dedupe UNIQUE(recipient_user_id, dedupe_key)
        );
        CREATE INDEX ix_notifications_recipient_time
          ON notifications(recipient_user_id, created_at);

        CREATE TABLE analytics_events (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE RESTRICT,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          event_type varchar(80) NOT NULL,
          idempotency_key varchar(160) NOT NULL,
          properties jsonb NOT NULL DEFAULT '{}'::jsonb,
          occurred_at timestamptz NOT NULL DEFAULT now(),
          received_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_analytics_events_idempotency UNIQUE(website_id, idempotency_key)
        );
        CREATE INDEX ix_analytics_events_website_time
          ON analytics_events(website_id, occurred_at);

        CREATE TABLE chatbots (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          website_id uuid NOT NULL UNIQUE REFERENCES websites(id) ON DELETE RESTRICT,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          public_id varchar(80) NOT NULL UNIQUE,
          state varchar(20) NOT NULL DEFAULT 'REQUESTED',
          active_index_id uuid,
          configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
          version integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_chatbots_state CHECK (
            state IN ('REQUESTED','INDEXING','ACTIVE','FAILED','DISABLED')
          )
        );

        CREATE TABLE chatbot_knowledge_indexes (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          chatbot_id uuid NOT NULL REFERENCES chatbots(id) ON DELETE RESTRICT,
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE RESTRICT,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          website_version_id uuid NOT NULL REFERENCES website_versions(id) ON DELETE RESTRICT,
          embedding_model varchar(160) NOT NULL,
          embedding_dimension integer NOT NULL,
          chunker_version varchar(40) NOT NULL,
          artifact_key varchar(1024),
          artifact_checksum varchar(64),
          manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
          state varchar(24) NOT NULL DEFAULT 'REQUESTED',
          failure_code varchar(100),
          created_at timestamptz NOT NULL DEFAULT now(),
          activated_at timestamptz,
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_chatbot_knowledge_indexes_state CHECK (
            state IN ('REQUESTED','EXTRACTING','EMBEDDING','BUILDING','VALIDATING','ACTIVE','SUPERSEDED','FAILED','DELETED')
          ),
          CONSTRAINT uq_chatbot_index_website_version UNIQUE(website_id, website_version_id)
        );
        ALTER TABLE chatbots ADD CONSTRAINT fk_chatbots_active_index
          FOREIGN KEY (active_index_id) REFERENCES chatbot_knowledge_indexes(id) ON DELETE RESTRICT;
        CREATE UNIQUE INDEX uq_chatbot_active_index_website
          ON chatbot_knowledge_indexes(website_id) WHERE state = 'ACTIVE';
        CREATE INDEX ix_chatbot_indexes_website_state
          ON chatbot_knowledge_indexes(website_id, state, created_at);

        CREATE TABLE chatbot_knowledge_chunks (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          knowledge_index_id uuid NOT NULL REFERENCES chatbot_knowledge_indexes(id) ON DELETE RESTRICT,
          chunk_key varchar(120) NOT NULL,
          source_page_path varchar(1024) NOT NULL,
          source_component_path varchar(1024) NOT NULL,
          content text NOT NULL,
          token_count integer NOT NULL,
          checksum varchar(64) NOT NULL,
          faiss_id integer NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_chatbot_chunks_key UNIQUE(knowledge_index_id, chunk_key),
          CONSTRAINT uq_chatbot_chunks_faiss_id UNIQUE(knowledge_index_id, faiss_id)
        );
        CREATE INDEX ix_chatbot_chunks_index
          ON chatbot_knowledge_chunks(knowledge_index_id, faiss_id);

        CREATE TABLE chat_conversations (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          chatbot_id uuid NOT NULL REFERENCES chatbots(id) ON DELETE RESTRICT,
          website_id uuid NOT NULL REFERENCES websites(id) ON DELETE RESTRICT,
          owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          access_token_hash varchar(64) NOT NULL,
          state varchar(20) NOT NULL DEFAULT 'OPEN',
          consent jsonb NOT NULL DEFAULT '{}'::jsonb,
          lead_id uuid REFERENCES leads(id) ON DELETE RESTRICT,
          started_at timestamptz NOT NULL DEFAULT now(),
          ended_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_chat_conversations_state CHECK (state IN ('OPEN','CLOSED','ARCHIVED'))
        );
        CREATE INDEX ix_chat_conversations_website_created
          ON chat_conversations(website_id, created_at);

        CREATE TABLE chat_messages (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          conversation_id uuid NOT NULL REFERENCES chat_conversations(id) ON DELETE RESTRICT,
          sequence integer NOT NULL,
          role varchar(20) NOT NULL,
          content text NOT NULL,
          retrieval jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_chat_messages_role CHECK (role IN ('USER','ASSISTANT','SYSTEM')),
          CONSTRAINT uq_chat_messages_sequence UNIQUE(conversation_id, sequence)
        );
        CREATE INDEX ix_chat_messages_conversation
          ON chat_messages(conversation_id, sequence);

        INSERT INTO platform_metadata(key, value, version)
          VALUES ('lead_zero_balance_policy', '{"policy":"ALLOW_DEBT"}'::jsonb, 1)
          ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM platform_metadata WHERE key = 'lead_zero_balance_policy';
        DROP TABLE chat_messages;
        DROP TABLE chat_conversations;
        DROP TABLE chatbot_knowledge_chunks;
        DROP INDEX ix_chatbot_indexes_website_state;
        DROP INDEX uq_chatbot_active_index_website;
        ALTER TABLE chatbots DROP CONSTRAINT fk_chatbots_active_index;
        DROP TABLE chatbot_knowledge_indexes;
        DROP TABLE chatbots;
        DROP TABLE analytics_events;
        DROP TABLE notifications;
        DROP TRIGGER trg_forbid_lead_credit_ledger_mutation ON lead_credit_ledger;
        DROP FUNCTION forbid_lead_credit_ledger_mutation();
        DROP TABLE lead_credit_ledger;
        DROP TABLE lead_credit_accounts;
        DROP INDEX ix_leads_website_source;
        DROP INDEX ix_leads_owner_captured;
        ALTER TABLE leads DROP CONSTRAINT ck_leads_status;
        ALTER TABLE leads DROP COLUMN version;
        ALTER TABLE leads DROP COLUMN retention_until;
        ALTER TABLE leads DROP COLUMN status;
        ALTER TABLE leads DROP COLUMN consent;
        ALTER TABLE leads DROP COLUMN page_path;
        ALTER TABLE leads DROP COLUMN source_reference_id;
        """
    )