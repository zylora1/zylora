# Zylora V2 system architecture

Status: **Frozen for Phase 1 implementation**

## Architectural goals

The architecture optimizes for deterministic ownership, tenant isolation, durable commercial state,
safe retries, reversible deployments, testable domain rules, and a Template catalog that can scale
without turning the editor into an arbitrary code execution surface.

## Context and trust zones

```text
Anonymous visitor ──> Public Zylora Web ───────┐
User browser ───────> User Portal / Editor ────┼──> FastAPI /api/v1
Admin browser ──────> Isolated Admin Web ──────┤         │
Customer visitor ──> Published Website Edge ──┘         ├── PostgreSQL
                                                        ├── Redis
Provider webhooks ─> Signed webhook endpoints ──────────┤
                                                        └── Transactional outbox
                                                                  │
                                                                  v
                                                            Celery workers
                                                              │  │  │
                           Object storage <────────────────────┘  │  └── Provider adapters
                           FAISS artifacts <───────────────────────┘
```

The four browser surfaces do not share authorization assumptions:

- Public Zylora Web is indexable where appropriate and contains no private account data.
- User Portal and Editor require a `USER` session and resource ownership checks.
- Super Admin Web uses an isolated host/route, cookie name, session audience, CSP, and authorization
  policy and requires `SUPER_ADMIN` on every API operation.
- Published customer Websites serve immutable build artifacts and use narrowly scoped public APIs for
  analytics, chatbot, and Lead submission.

## Monorepo boundaries

```text
apps/
  web/                 Next.js public site, User portal, editor, Admin UI
  api/                 FastAPI HTTP application and canonical domain services
  worker/              Celery entry points and task adapters
packages/
  ai/                  AI/embedding ports, patch planning, cost metering
  contracts/           generated OpenAPI clients and shared API types
  config/              shared non-secret tooling/build configuration
  ui/                  Zylora design-system primitives
  template-schema/     JSON Schema, migrations, registry, validators
  shared/              side-effect-free shared TypeScript utilities only
docs/                  architecture, product, design, security, testing, operations
infra/                 local and deployment infrastructure definitions
scripts/               repeatable developer, validation, and operational commands
```

Python packages remain under their owning application unless a genuinely shared, independently
testable Python package emerges. TypeScript packages must not import server secrets or backend domain
logic. `packages/contracts` represents transport shapes, not authorization or entitlement rules.

## Runtime components

### Next.js Web

Responsibilities:

- server-rendered public marketing, Blog, Template discovery, and legal pages;
- User portal, editor shell, responsive previews, and evaluated server state;
- isolated Super Admin route group/host mapping;
- secure API client, CSRF token handling, accessibility, metadata, sitemap, and robots policy;
- deterministic rendering of structured Template/Website documents through the component registry.

It may perform presentation validation for immediate feedback. It never decides ownership,
entitlement, price, payment success, publish eligibility, credit deduction, or admin authorization.

### FastAPI API

The API is a modular monolith with explicit domain packages. This keeps transactions and invariants
local while avoiding a premature distributed system. Each domain exposes an application service and
repository/port interfaces; HTTP routers translate contracts and never contain business rules.

Canonical domains:

| Domain | Canonical services |
| --- | --- |
| Identity | `AuthenticationService`, `SessionService`, `AuthorizationService` |
| Templates | `TemplateValidationService`, `TemplateCatalogService` |
| Websites | `WebsiteService`, `OwnershipService`, `WebsiteVersionService` |
| Editor/AI | `PatchValidationService`, `AiEditingService` |
| Commercial | `WebsiteRequirementService`, `EntitlementService`, `PlanRecommendationService` |
| Billing | `PaymentService`, `SubscriptionService`, `InvoiceService` |
| Publishing | `PublishEligibilityService`, `DeploymentService`, `DomainService` |
| Transfer/export | `OwnershipTransferService`, `WebsiteExportService`, `AccountExportService` |
| Leads/credits | `LeadService`, `CreditLedgerService`, `ZeroCreditPolicyService` |
| Chatbot | `KnowledgeIndexService`, `ChatbotService` |
| Analytics | `AnalyticsIngestionService`, `AnalyticsQueryService` |
| Messaging | `NotificationService`, `EmailService`, `CampaignService` |
| Content/admin | `BlogService`, `PlatformConfigurationService`, `AuditService` |

Modules communicate by typed application commands or domain events. They do not reach into one
another's tables from HTTP handlers. Cross-domain workflows are orchestration services with explicit
transaction ownership.

### PostgreSQL

PostgreSQL is authoritative for identity, ownership, lifecycle, pricing, entitlements, commercial
records, idempotency, durable jobs, audit, and metadata. Important invariants use constraints,
partial unique indexes, foreign keys, row locks, serializable/advisory locking where appropriate,
and deferred constraint triggers.

All timestamps are timezone-aware UTC. IDs are UUIDv7-compatible values generated by the application
or a supported database function. Human-facing slugs are separate. Money is integer minor units plus
an explicit uppercase ISO currency. Mutable rows carry a monotonic `version` for optimistic
concurrency.

### Redis and Celery

Redis provides cache, rate-limit counters, distributed leases for non-authoritative work, and Celery
transport. Losing Redis may delay work or invalidate caches but cannot lose commercial truth. Durable
job intent begins in the PostgreSQL outbox within the same transaction as the state change.

An outbox dispatcher publishes a stable event ID. Workers claim a job idempotently, record attempts,
heartbeat long work, use bounded exponential backoff with jitter, and move exhausted jobs to a
dead-letter state visible to operations. A worker calls the same domain transition APIs as HTTP code;
it does not write arbitrary final states.

### Object storage

An S3-compatible boundary stores uploaded/processed assets, Template assets, Blog/OG images,
deployment bundles, ZIP exports, account exports, and encrypted/versioned FAISS artifacts. Storage is
private by default. Public assets use immutable content-hashed keys; private downloads use short-lived
signed URLs bound to an authorized artifact record. Application disk is only bounded scratch/cache.

### FAISS

FAISS is a derived retrieval index, never the knowledge source of record. Published Website content,
chunks, embedding metadata, and index manifests live in PostgreSQL/object storage. Each index artifact
belongs to exactly one `website_id`, `owner_user_id`, published `website_version_id`, embedding model,
dimension, and checksum.

Workers build into a new private prefix, validate manifest/checksum/search smoke tests, and atomically
update the active index pointer. Query APIs require the resolved Website ID and load only its active
manifest. There is no global cross-Website search path. Local worker cache paths use opaque hashes,
path containment checks, locks, atomic replacement, bounded cache eviction, and no client-supplied
filesystem segments.

## Core workflows

### Create from Template

1. API resolves a published, approved Template version.
2. One transaction inserts Website, initial ownership, immutable initial WebsiteVersion, current
   version pointer, and audit/outbox records.
3. The Website remains private `DRAFT`; no domain, deployment, or analytics is fabricated.

### Autosave/edit

The client sends an expected document version and typed patch. The server authorizes ownership,
validates patch paths/operations and schema, rejects stale writes with the current version, creates an
immutable WebsiteVersion, and atomically advances the draft pointer. AI and manual requests use the
same operation pipeline and differ only in source/provenance.

### Publish

`PublishEligibilityService` evaluates canonical requirements and returns a signed-to-session,
short-lived evaluation identifier for UX. The publish command re-evaluates inside a locked
transaction, reserves the one-live-site marker and domain, snapshots billing/entitlements and Website
version, creates Deployment `QUEUED`, and writes an outbox event. Workers build a new immutable
artifact, provision route/TLS, health-check, then switch traffic and mark Website published in a final
transaction. Failure releases reservations and preserves the current live deployment.

### Transfer

Draft transfer can proceed directly under a locked Website row. A live Website enters transfer
preparation, blocks edits/publishes, and disables routing before the final transaction. The final
transaction closes the old ownership, inserts the recipient ownership, clears old domain/billing/live
associations, sets `TRANSFERRED`, rotates resource access epochs, audits, and emits notifications.

### Lead capture

A public endpoint resolves Website from a server-owned site token/host mapping, validates origin and
payload, applies bot/rate controls, and passes the normalized submission plus idempotency key to
`LeadService`. One DB transaction locks the credit account, enforces centralized zero-balance policy,
inserts Lead and one ledger entry, analytics event, notification intent, and idempotent response.

### Payment webhook

The raw body is size-limited and signature-verified before parsing. `PaymentService` persists provider
event ID/hash, detects duplicates/replays, resolves the expected local payment, queries the provider
when required, checks amount/currency/product, and performs an allowed state transition. Capabilities
derive only from trusted local state after commit.

## Provider ports

Provider boundaries are deliberately narrow:

- `PaymentProvider`: checkout, payment verification, webhook verification, reconciliation, refund
  where supported;
- `DomainProvider`: hostname create/read/delete, verification status, TLS/route status;
- `ObjectStorage`: put, stat, read, delete, signed upload/download, lifecycle metadata;
- `EmailProvider`: transactional send, marketing send, delivery event verification;
- `OAuthProvider`: authorization URL and callback identity verification;
- `AiProvider` / `EmbeddingProvider`: structured generation/embedding plus usage metadata;
- `MalwareScanner`: bounded stream/file scan;
- `TelemetrySink`: errors/traces/metrics without business authority.

Production startup validates required adapters for enabled capabilities. Optional provider failure
degrades that capability and surfaces health; it does not fabricate success or necessarily fail the
entire API readiness check.

## Configuration

Configuration is split into:

- static source-controlled defaults and schemas;
- environment-specific non-secret configuration;
- secret-manager values;
- versioned Super-Admin business configuration in PostgreSQL.

Only explicitly public values receive a browser-exposed prefix. Production refuses unsafe debug
auth, default secrets, wildcard trusted hosts, local durable storage, or missing cryptographic keys.
Business prices and entitlements never come from environment variables.

## Consistency and failure model

- Database commit occurs before external side effects; outbox guarantees retryable intent.
- At-least-once delivery is expected, so every handler has an idempotency boundary.
- External references store provider ID, request idempotency key, response hash/status, and
  correlation ID without secrets.
- State transitions use compare-and-set/row locks and reject stale or illegal commands.
- User-visible operations expose pending/failed/retryable states rather than optimistic success.
- Compensations are explicit: release reservations, deactivate partially created routes, expire
  artifacts, or restore the prior deployment pointer.

## Scalability direction

Start as a modular monolith with horizontally scalable stateless Web/API processes and separately
scalable worker queues. Use server-side pagination/search; partition high-volume analytics/audit/event
tables when measured volume warrants it. Template rendering and published assets favor immutable CDN
caching. Database read replicas, dedicated analytics storage, or service extraction require measured
pressure and an ADR; they are not Phase 1 assumptions.

## Prohibited shortcuts

- No arbitrary Template JavaScript, raw HTML persistence, or runtime code evaluation.
- No direct browser access to databases, object storage credentials, FAISS paths, or provider secrets.
- No frontend-only ownership, entitlement, price, or payment decisions.
- No Redis-only locks for relational invariants.
- No global vector index or client-selected tenant key.
- No synchronous request waiting for long deployments, index builds, campaigns, or ZIP generation.
- No direct state mutation that bypasses canonical transition services and audit/outbox records.
