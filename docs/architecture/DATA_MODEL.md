# Zylora V2 relational data model

Status: **Logical model frozen; physical DDL begins in Phase 1/2**

## Conventions

- PostgreSQL is the system of record.
- Primary keys are UUIDs suitable for time-ordered generation; public slugs/tokens are separate.
- Timestamps are `timestamptz` in UTC and use `created_at`, `updated_at`, and effective ranges where
  applicable.
- Money uses `amount_minor bigint CHECK (amount_minor >= 0)` and `currency char(3)` constrained to
  uppercase configured ISO 4217 values. Negative ledger movements use signed `delta` fields.
- Mutable aggregate roots carry `version bigint NOT NULL DEFAULT 1` for optimistic concurrency.
- Enum values use named PostgreSQL enums or constrained text with migrations; arbitrary strings are
  not accepted.
- JSONB stores versioned documents or provider evidence, never relationships that require foreign
  keys. JSON schemas and payload sizes are validated at the application boundary.
- Owner-scoped query indexes start with `owner_user_id` or `website_id`; public identifiers remain
  globally unique.
- Financial, ownership, audit, ledger, published-version, and deployment history is append-only or
  effective-dated.

## Identity and authentication

### `users`

| Column | Notes |
| --- | --- |
| `id` | PK |
| `account_type` | exactly `USER` or `SUPER_ADMIN` |
| `email_normalized` | unique, Unicode/case normalization policy applied |
| `email_display` | original safe display form |
| `password_hash` | nullable only for OAuth-only account; Argon2id encoded hash |
| `status` | `PENDING_VERIFICATION`, `ACTIVE`, `LOCKED`, `DELETION_PENDING`, `DELETED` |
| `email_verified_at` | null until server verification |
| `auth_epoch` | incremented to revoke all sessions/resource tokens |
| `locale`, `timezone` | validated preferences |
| timestamps/version | standard fields |

Constraints:

- `CHECK account_type IN ('USER','SUPER_ADMIN')`.
- partial unique index on constant expression where `account_type='SUPER_ADMIN'` permits at most one.
- production bootstrap/readiness verifies exactly one active Super Admin.
- active account requires `email_verified_at`; OAuth callback writes it only after provider proof.

### `super_admin_profiles`

One-to-one extension keyed by `user_id`; contains admin-specific security policy metadata, not a new
role hierarchy. Service and deferred trigger require the referenced User to be `SUPER_ADMIN`.

### `auth_identities`

Links a User to `PASSWORD` or `GOOGLE` identity. Unique `(provider, provider_subject)` and unique
`(user_id, provider)`. Provider email alone is never a subject key. Stores no OAuth access token
unless a future approved feature requires encrypted, scoped storage.

### `sessions`

Stores a hash of the opaque session token, `user_id`, audience (`USER_WEB` or `ADMIN_WEB`), CSRF
secret hash/rotation metadata, issued/last-seen/expires timestamps, IP prefix and user-agent/device
metadata, revoked time/reason, and `auth_epoch_at_issue`. User and admin audiences cannot be exchanged.
Indexes support active sessions by User and expiry cleanup.

### Verification and recovery

- `email_verifications`: User/email, purpose, HMAC/Argon2-protected code digest, expiry, consumed time,
  attempt count, send generation, and superseded time. One current verification per purpose/User.
- `password_resets`: token digest, User, expiry, consumed/revoked time, request context.
- `auth_attempts`: privacy-minimized IP/account hash, route, outcome, risk reason, challenge state, and
  timestamp for abuse analysis. High-volume retention is bounded.

## Templates and structured documents

### `templates`

Stable catalog identity: slug, lifecycle (`DRAFT`, `ACTIVE`, `DEPRECATED`, `RETIRED`), current published
version pointer, featured/order metadata, aggregate popularity counters, and timestamps. It contains
no uncontrolled HTML.

### `template_versions`

Immutable rows containing `template_id`, monotonic version number, schema version, structured JSONB
document, content checksum, changelog, provenance/asset manifest, requirements snapshot, creator,
status, validation summary, approval actor/time, publish time, and deprecation metadata.

Constraints:

- unique `(template_id, version_number)` and checksum index;
- published requires approved and most recent successful validation for the same checksum/validator
  version;
- `templates.current_published_version_id` uses a composite FK proving the version belongs to the
  Template;
- public catalog query admits only `PUBLISHED` versions of active Templates.

### Classification and validation

- `template_categories`: hierarchical category with unique slug and optional parent.
- `template_tags`: unique normalized tag slug.
- `template_category_links`, `template_tag_links`: explicit many-to-many join tables.
- `template_validations`: append-only run per version/checksum with validator version, status,
  individual check results, browser matrix, performance measurements, logs/artifact references,
  started/completed timestamps, and approver decision.
- `template_assets`: content-hashed object key, MIME detected server-side, bytes/dimensions, license
  and provenance metadata, processing state, and references. No secrets or arbitrary remote runtime
  URLs.

## Websites, versions, and ownership

### `websites`

Stable project identity with lifecycle state, normalized display name/slug, source Template and exact
source version, current draft version, published version, active deployment, `live_owner_user_id`,
access epoch, and timestamps/version.

Constraints:

- source Template/version are non-null and must reference an approved published version at creation;
- version pointers use composite FKs `(website_id, website_version_id)`;
- `live_owner_user_id` is non-null exactly while lifecycle is `PUBLISHED`;
- partial unique index on `live_owner_user_id WHERE live_owner_user_id IS NOT NULL` enforces one live
  Website per User;
- active deployment/published version must belong to the same Website.

### `website_versions`

Immutable structured Website snapshots: Website, monotonic version, parent version, schema version,
document JSONB, checksum, source (`TEMPLATE`, `MANUAL`, `AI`, `RESTORE`, `SYSTEM_MIGRATION`), actor,
AI usage reference when applicable, edit summary, validation status/results, and created time. Unique
`(website_id, version_number)` and optional deduplication by `(website_id, checksum)`.

### `website_ownerships`

Effective-dated ownership history: Website, owner User, `started_at`, nullable `ended_at`, transfer
operation ID, acquisition reason, and actor/request evidence.

Database invariants:

- partial unique index on `website_id WHERE ended_at IS NULL` prevents two current owners;
- a deferred constraint trigger checks exactly one open ownership row for every non-deleted Website at
  transaction commit;
- current owner lookup always uses the open row; no duplicate owner boolean exists;
- transfer locks the Website and open ownership row, closes it, inserts the next row, rotates access
  epoch, and audits within one transaction.

### `ownership_transfers`

Command/workflow record with sender, recipient, Website, state, idempotency key, expiry (if approval is
introduced), routing-deactivation dependency, failure code, completed time, and correlation ID.
Unique `(website_id)` for active transfer states prevents concurrent transfers.

## Domains and deployments

### `domains`

Website, owner snapshot, type (`ZYLORA_SUBDOMAIN`, `CUSTOM`), normalized ASCII hostname, display value,
verification/state fields, DNS challenge digest/value reference, provider hostname ID, TLS status,
active flag, last checked time, retry/failure metadata, and version.

Constraints include globally unique normalized hostname, reserved-name rejection in canonical service,
one active primary domain per Website, and owner/Website relationship validation. Provider secrets are
never stored here.

### `deployments`

Immutable attempt record: Website/version, initiating owner, destination/domain, entitlement/catalog
snapshot, build artifact key/checksum, state, previous deployment, provider route reference, queued/
started/health-checked/switched/completed times, failure code/safe message/log artifact, and rollback
metadata. Unique idempotency key per Website and one active attempt per Website.

### `deployment_events`

Append-only transition/evidence log with deployment, from/to state, actor/job, correlation ID,
provider evidence hash, and timestamp. Large raw logs live in private object storage with retention.

## Plans, subscriptions, and billing

### `plan_catalogs`

Immutable commercial snapshot with state (`DRAFT`, `PUBLISHED`, `RETIRED`), effective time, version,
creator, publisher, and notes. Only one catalog is current for a market/currency/interval selection.
A deferred constraint trigger/service permits publish only when it contains exactly four valid plans.

### `plans`

Catalog-scoped plan with stable internal code, editable display name/description, slot/display order
1–4, active/visible state, recommendation weight, and timestamps. Unique `(catalog_id, slot)` and
`CHECK slot BETWEEN 1 AND 4`; no code branches on name or slot.

### `plan_prices`

Plan, amount minor, currency, interval/unit, tax behavior, effective range, active flag, and source.
Exclusion constraints prevent overlapping active effective ranges for the same plan/currency/interval.

### `plan_entitlements`

Plan plus capability key and exactly one typed value (`bool`, `int`, `decimal-as-string`, or enum),
unit, comparison operator, and metadata. Unique `(plan_id, capability_key)`. Capability definitions
come from a versioned registry; plans do not contain arbitrary unchecked keys.

### `subscriptions`

User, selected plan/catalog/price snapshots, state, period bounds, cancellation settings, provider
customer/subscription references, last trusted payment, version, and timestamps. Partial unique index
prevents more than one current subscription in capability-granting/pending-renewal states per User.

### `invoices`

Immutable number, User/subscription, line-item snapshot JSON validated by an invoice schema, subtotal/
tax/total minor units, currency, state, issued/due/paid times, provider reference, and immutable render
artifact. Totals are recomputed server-side and constrained nonnegative.

### `payments` and `payment_events`

`payments` stores local purpose (`SUBSCRIPTION`, `EXPORT`), expected amount/currency, state, selected
provider identifier, provider payment/order reference, idempotency key, trusted verification time,
and reconciliation metadata. It references exactly one local payable through a constrained association.

`payment_events` is append-only: provider event ID, event type, received time, raw-body hash, signature
result, normalized payload/evidence (redacted), processing outcome, replay linkage, and correlation ID.
Unique `(provider, provider_event_id)` and `(provider, provider_payment_id, terminal_event_type)` stop
duplicates. Raw sensitive payload retention is minimized/encrypted.

### `export_purchases` and artifacts

Export purchase stores Website/version/owner, exact admin price setting version, amount/currency
snapshot, state, payment, generation attempt, and expiry. Capability is available only in `READY` with
trusted payment `CAPTURED/SETTLED` according to the provider contract.

- `website_export_artifacts`: private object key/checksum/size, manifest, generated/expiry/deleted
  timestamps, and download audit counter.
- `account_export_requests`: separate purpose/state and privacy data manifest.
- `account_export_artifacts`: separate bucket prefix/content type; a DB check and generator contract
  prohibit Website deployment/source bundles.

No FK or state transition allows an account export to satisfy an ExportPurchase.

## Leads and credits

### `leads`

Website, current owner snapshot, source (`FORM`, `CHATBOT`), source reference/conversation, normalized
name/email/phone/enquiry, page, consent evidence/version where applicable, status, idempotency key,
captured time, privacy retention date, and version. Sensitive contact fields may use application-level
encryption/search digests where threat modeling warrants it.

Unique `(website_id, source, idempotency_key)` returns the original successful Lead on retry.

### `lead_credit_accounts`

One per User, with optionally cached balance and version. The cached balance is validated against the
ledger and never replaces it as audit truth.

### `lead_credit_ledger`

Append-only User account, signed integer delta, type (`PURCHASE`, `LEAD_CAPTURE`, `ADMIN_GRANT`,
`REFUND`, `CORRECTION`), Lead/payment/admin action reference, idempotency key, resulting balance,
actor, reason, and timestamp. Unique idempotency key per account; `LEAD_CAPTURE` requires `delta=-1`
and unique `lead_id`. A DB trigger forbids update/delete outside an exceptional audited maintenance
procedure.

## Chatbot knowledge and conversations

- `chatbots`: one per Website, state, public bot identifier, configuration, active index, and version.
- `chatbot_knowledge_indexes`: Website, owner, published WebsiteVersion, embedding model/dimension,
  chunker version, artifact key/checksum, manifest, state, superseded index, and timestamps. One active
  index per Website; no global index row.
- `chatbot_knowledge_chunks`: index, stable chunk ID, source page/component path, redacted text or
  durable source reference, token count, checksum, and FAISS integer ID unique within index.
- `chat_conversations`: Website/Chatbot, opaque visitor/session identifier, consent/retention metadata,
  state, start/end times, optional resulting Lead.
- `chat_messages`: conversation, sequence, role, content or encrypted/redacted content, retrieval
  evidence (chunk IDs only from the same index), model usage, latency, and created time.

Composite foreign keys ensure conversation, index, chunks, and Website identities match.

## Analytics and notifications

### `analytics_events`

Append-only event ID/idempotency key, Website, published version, owner snapshot, type, occurred/
received times, privacy-safe visitor/session IDs, page/referrer/device properties, consent category,
and bounded properties. Partition by time when needed; unique event ID supports retry.

### `analytics_daily_rollups`

Phase 11 stores tenant-scoped daily totals by `(website_id, timezone, bucket_date)`: page views,
sessions, consent-available visitors, Leads by source, chatbot conversations/messages, conversions,
event count, and refresh time. The unique bucket key supports idempotent recomputation. Portal reads
these rollups only and displays no metrics until recorded activity is meaningful.

### `notifications`

Recipient User, server-authored type/title/body/deep link, resource reference, `UNREAD`/`READ`/`ARCHIVED`
state, read time, dedupe key, and timestamps. Unique `(recipient_user_id, dedupe_key)` and recipient-state
index support retry-safe private inbox delivery and pagination; unsafe customer-authored HTML/links are
not persisted.

### `transactional_emails`

Recipient User/resource reference, approved transactional kind, encrypted recipient and rendered
content, stable idempotency key, attempt/next-attempt/provider/safe-error fields, and state. The unique
idempotency key links one durable outbox event to at-least-once provider delivery without storing email
content in the outbox payload. This is distinct from marketing campaign/delivery tables.

## Campaigns, suppression, and Blog

- `campaigns`: creator, state, audience query snapshot, content/template version, schedule, consent
  category, counters derived from deliveries, and audit metadata.
- `campaign_recipients`: immutable resolved audience snapshot with suppression decision/reason.
- `campaign_delivery_events`: immutable recipient/provider acceptance, failure, bounce, complaint, and unsubscribe facts; campaign recipient state is the current delivery projection.
- `email_suppressions`: recipient reference, scope/reason/source,
  hard-bounce/complaint/unsubscribe evidence, and effective time. Marketing suppression never blocks
  security/transactional email.
- `blog_posts`: author Super Admin, slug, structured content, state, scheduled/published time, SEO and
  social metadata, canonical, version, and current render artifact.
- `blog_categories`, `blog_tags`, and join tables: normalized unique slugs and metadata.
- `blog_post_versions`: immutable content/SEO snapshots for preview, restore, and audit.

## Platform operations

- `audit_logs`: append-only actor/subject, action, resource type/ID, redacted old/new values, IP,
  request/correlation ID, reason, and timestamp. Sensitive values are excluded at the serializer.
- `platform_settings`: typed, versioned settings with effective range, scope, encrypted flag where
  appropriate, actor, and audit link. Business settings include export price and zero-credit policy;
  secrets remain in a secret manager.
- `idempotency_records`: scope, key hash, actor/resource, request fingerprint, state, response status/
  body reference, and expiry. Same key with a different fingerprint is rejected.
- `outbox_events`: aggregate, event type/version, payload, state, attempt/lease times, and correlation.
- `job_runs`: outbox event/task, queue, idempotency key, state, attempt, heartbeat, safe error,
  dead-letter and retry metadata.
- `feature_flags`: only justified rollout flags with owner, default, targeting, created/expiry/removal
  criteria. A validation rule rejects names or payloads referencing removed V1 architecture.

## Referential and deletion policy

| Data | Deletion behavior |
| --- | --- |
| Sessions/verification | revoke then delete after short retention |
| Draft documents/assets | soft-delete grace period, then purge objects and rows where allowed |
| Live Website | unpublish and detach domains before purge workflow |
| Ownership/audit/ledger | retain immutable history with minimized/anonymized identity where lawful |
| Payments/invoices | retain for statutory/accounting period; never cascade from User |
| Leads/conversations | configurable retention and erasure/anonymization workflow |
| Analytics raw events | short bounded retention; aggregates longer when privacy-safe |
| ZIP/account exports | expire and delete automatically |
| FAISS | delete on Website purge/owner change; rebuildable from authorized published source |

Direct `ON DELETE CASCADE` is reserved for non-audited child data that cannot outlive its parent.
Commercial and audit tables use `RESTRICT` plus explicit lifecycle services. Account deletion is a
tracked workflow, not `DELETE FROM users`.

## Isolation and query rules

Every User-owned repository method receives the authenticated `user_id` and constrains by both owner
and resource ID. Website children are authorized through the current ownership join, not a
client-supplied owner ID. Super Admin access uses separate methods and always audits sensitive reads/
writes.

PostgreSQL row-level security may be enabled as defense in depth for mature owner-scoped tables after
connection session context and worker behavior are proven. RLS is never the only authorization layer,
and migration/service roles never serve HTTP requests.

## Concurrency recipes

- Publish: lock User live-site key/advisory lock plus Website row; reserve unique
  `live_owner_user_id` before job dispatch.
- Transfer: lock Website and current ownership; active-transfer unique index; deferred ownership
  invariant at commit.
- Lead/credit: lock credit account; unique Lead idempotency and unique ledger `lead_id`; one commit.
- Payment: unique provider event; lock local payment; compare expected amount/currency/purpose.
- Subdomain: normalized hostname unique index; insert reservation inside publish transaction.
- Plan change: edit immutable draft catalog; validate four plans; atomically publish catalog pointer.
- ZIP generation: unique active generation for purchase; payment state predicate checked again by
  worker before writing artifact.
