# ruff: noqa: E501
"""super-admin campaigns and SEO Blog publishing

Revision ID: 20260818_0013
Revises: 20260817_0012
"""

from collections.abc import Sequence

from alembic import op

revision: str = '20260818_0013'
down_revision: str | None = '20260817_0012'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE campaigns (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          name varchar(160) NOT NULL,
          subject varchar(200) NOT NULL,
          body text NOT NULL,
          state varchar(20) NOT NULL DEFAULT 'DRAFT',
          audience_type varchar(32) NOT NULL,
          audience_plan_code varchar(20),
          audience_snapshot_count integer NOT NULL DEFAULT 0,
          scheduled_at timestamptz,
          started_at timestamptz,
          completed_at timestamptz,
          failure_code varchar(100),
          version integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_campaigns_state CHECK (state IN ('DRAFT','READY','SCHEDULED','SENDING','COMPLETED','PAUSED','CANCELLED','FAILED')),
          CONSTRAINT ck_campaigns_audience CHECK (audience_type IN ('ALL_USERS','FREE_USERS','PAID_USERS','PLAN_USERS','RECENT_USERS','HAS_DRAFT','NO_PUBLISHED_WEBSITE')),
          CONSTRAINT ck_campaigns_plan_audience CHECK ((audience_type = 'PLAN_USERS' AND audience_plan_code IN ('FREE','BASIC','GROWTH','BUSINESS')) OR (audience_type <> 'PLAN_USERS' AND audience_plan_code IS NULL))
        );
        CREATE INDEX ix_campaigns_state_schedule ON campaigns(state, scheduled_at, created_at);

        CREATE TABLE campaign_recipients (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          campaign_id uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
          recipient_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          recipient_ciphertext bytea NOT NULL,
          unsubscribe_token_digest bytea NOT NULL,
          unsubscribe_token_ciphertext bytea NOT NULL,
          idempotency_key varchar(200) NOT NULL,
          state varchar(20) NOT NULL DEFAULT 'PENDING',
          suppression_reason varchar(100),
          attempts integer NOT NULL DEFAULT 0,
          provider_message_id varchar(200),
          last_error_code varchar(100),
          sent_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_campaign_recipients_state CHECK (state IN ('PENDING','SUPPRESSED','SENDING','SENT','DELIVERED','FAILED','BOUNCED','COMPLAINED','UNSUBSCRIBED')),
          CONSTRAINT uq_campaign_recipients_user UNIQUE(campaign_id, recipient_user_id),
          CONSTRAINT uq_campaign_recipients_idempotency UNIQUE(idempotency_key),
          CONSTRAINT uq_campaign_recipients_unsubscribe UNIQUE(unsubscribe_token_digest)
        );
        CREATE INDEX ix_campaign_recipients_delivery ON campaign_recipients(campaign_id, state, created_at);

        CREATE TABLE email_suppressions (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          recipient_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          scope varchar(20) NOT NULL DEFAULT 'MARKETING',
          reason varchar(100) NOT NULL,
          source varchar(60) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_email_suppressions_scope CHECK (scope IN ('MARKETING','ALL_EMAIL')),
          CONSTRAINT uq_email_suppressions_user_scope UNIQUE(recipient_user_id, scope)
        );
        CREATE INDEX ix_email_suppressions_scope ON email_suppressions(scope, created_at);

        CREATE TABLE campaign_delivery_events (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          campaign_recipient_id uuid NOT NULL REFERENCES campaign_recipients(id) ON DELETE CASCADE,
          event_type varchar(20) NOT NULL,
          provider varchar(40) NOT NULL,
          provider_event_id varchar(200) NOT NULL,
          metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          occurred_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_campaign_delivery_events_type CHECK (event_type IN ('ACCEPTED','DELIVERED','BOUNCED','COMPLAINED','OPENED','CLICKED','UNSUBSCRIBED','FAILED')),
          CONSTRAINT uq_campaign_delivery_events_provider UNIQUE(provider, provider_event_id)
        );
        CREATE INDEX ix_campaign_delivery_events_recipient ON campaign_delivery_events(campaign_recipient_id, occurred_at);

        CREATE TABLE blog_posts (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          author_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          title varchar(180) NOT NULL,
          slug varchar(120) NOT NULL,
          excerpt varchar(500) NOT NULL,
          content text NOT NULL,
          featured_image_url varchar(1000),
          state varchar(20) NOT NULL DEFAULT 'DRAFT',
          seo_title varchar(180),
          meta_description varchar(320),
          canonical_url varchar(1000),
          og_title varchar(180),
          og_description varchar(320),
          scheduled_at timestamptz,
          published_at timestamptz,
          version integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_blog_posts_state CHECK (state IN ('DRAFT','READY','SCHEDULED','PUBLISHED','ARCHIVED')),
          CONSTRAINT uq_blog_posts_slug UNIQUE(slug)
        );
        CREATE INDEX ix_blog_posts_publication ON blog_posts(state, published_at, scheduled_at);
        CREATE TABLE blog_post_versions (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          post_id uuid NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
          author_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          version integer NOT NULL,
          rendered_html text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_blog_post_versions_number UNIQUE(post_id, version)
        );
        CREATE TABLE blog_categories (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          name varchar(80) NOT NULL,
          slug varchar(100) NOT NULL,
          CONSTRAINT uq_blog_categories_slug UNIQUE(slug)
        );
        CREATE TABLE blog_tags (
          id uuid PRIMARY KEY DEFAULT uuidv7(),
          name varchar(80) NOT NULL,
          slug varchar(100) NOT NULL,
          CONSTRAINT uq_blog_tags_slug UNIQUE(slug)
        );
        CREATE TABLE blog_post_categories (
          post_id uuid NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
          category_id uuid NOT NULL REFERENCES blog_categories(id) ON DELETE RESTRICT,
          PRIMARY KEY(post_id, category_id)
        );
        CREATE TABLE blog_post_tags (
          post_id uuid NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
          tag_id uuid NOT NULL REFERENCES blog_tags(id) ON DELETE RESTRICT,
          PRIMARY KEY(post_id, tag_id)
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE blog_post_tags;
        DROP TABLE blog_post_categories;
        DROP TABLE blog_tags;
        DROP TABLE blog_categories;
        DROP TABLE blog_post_versions;
        DROP TABLE blog_posts;
        DROP TABLE campaign_delivery_events;
        DROP TABLE email_suppressions;
        DROP TABLE campaign_recipients;
        DROP TABLE campaigns;
        """
    )