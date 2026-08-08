# Phase 0 decisions and V1 lessons

Status: **Frozen for implementation**
Decision date: 2026-08-08
Authority: `ZYLORA_MASTER_PROMPT.txt`

## Decision register

| ID | Decision | Status |
| --- | --- | --- |
| ADR-000 | V2 is a new monorepo; V1 remains read-only | Accepted |
| ADR-001 | Account types are only `USER` and `SUPER_ADMIN` | Accepted |
| ADR-002 | Data isolation uses owner and Website keys, not organizations or workspaces | Accepted |
| ADR-003 | A structured Template/Website document is the single editor format | Accepted |
| ADR-004 | PostgreSQL is authoritative; Redis and FAISS are derived/transient stores | Accepted |
| ADR-005 | FastAPI domain services own critical rules | Accepted |
| ADR-006 | Transactional outbox plus idempotent Celery jobs handles external side effects | Accepted |
| ADR-007 | Exactly one current owner is enforced by ownership rows and a deferred DB invariant | Accepted |
| ADR-008 | At most one live Website per User is enforced with a partial unique index | Accepted |
| ADR-009 | Public plan catalog contains exactly four data-driven plans | Accepted |
| ADR-010 | Payment adapter exists but no payment provider is approved or active in Phase 0 | Accepted |
| ADR-011 | Cloudflare is the preferred DNS/edge adapter; activation still requires configuration | Accepted |
| ADR-012 | FAISS indexes are isolated per Website and stored as private versioned artifacts | Accepted |
| ADR-013 | Paid Website ZIP and privacy/account export use separate domains and artifacts | Accepted |
| ADR-014 | Public, User, Super Admin, and customer Website surfaces are separate trust zones | Accepted |
| ADR-015 | V1 implementation is not copied; only verified patterns and lessons may inform V2 | Accepted |

## V1 read-only inspection

The V1 repository was inspected without modification. It contains useful evidence for the selected
stack and for operational requirements: a Next.js frontend, FastAPI API, PostgreSQL/Alembic,
Redis/Celery, Cloudflare custom-hostname integration, S3-compatible storage, FAISS utilities,
structured logging, health endpoints, audit records, and browser QA artifacts.

Useful patterns to redesign cleanly:

- row locking, append-only credit transactions, idempotency keys, and audit records;
- an explicit custom-domain provider protocol;
- FAISS path validation, per-Website directories, file locking, atomic manifest writes, and backup
  rotation;
- provider outage handling and liveness/readiness separation;
- immutable deployment/version concepts and server-side payment verification.

Patterns explicitly rejected:

- freelancer/client/staff roles, multiple customer portals, tenant-slug account containers, and
  permission matrices;
- provider selection derived from legacy code or environment variables;
- broad test coverage exclusions around core billing, publishing, domains, credits, and operations;
- overlapping lead, billing, pricing, ownership, and publishing implementations;
- local runtime data as a production durability strategy;
- patch reports and exception lists substituting for canonical architecture.

## Provider decisions

The specification does not approve a payment vendor. Therefore the architecture defines the
`PaymentProvider` port and deterministic test adapter but activates no commercial adapter. V1's
Razorpay integration is historical evidence only. Phase 7 may implement a production adapter only
after an explicit product decision records provider, markets, currencies, settlement, refunds,
webhook behavior, and operational ownership.

Cloudflare for SaaS is the preferred custom-domain and edge implementation because the master
specification names it as the default direction. It remains behind `DomainProvider`; missing
credentials disable custom-domain provisioning without fabricating success.

Email, object storage, Google OAuth, AI/model, embedding, malware scanning, and monitoring vendors
remain adapter choices. Phase implementation selects only the minimum approved adapters and always
ships deterministic test doubles.

## Consistency resolutions

- `Website.lifecycle_state` describes customer-visible lifecycle; `Deployment.state` describes an
  individual release attempt. They are not the same state machine.
- Current Website ownership is represented by one open `website_ownerships` row. A partial unique
  index prevents two open rows; a deferred constraint trigger prevents zero open rows at commit.
- The one-live-site invariant is implemented by `websites.live_owner_user_id`, present only while
  published, with a partial unique index. It is never inferred only from UI state.
- Transfers of live Websites first deactivate public routing. The final owner change is one DB
  transaction, after which the recipient follows the normal publish flow.
- Published plan catalogs are immutable snapshots containing exactly four plans. Admin changes are
  drafted and atomically published rather than mutating a live catalog into an invalid interim state.
- Redis loss may reduce noncritical functionality but cannot create paid access, duplicate credits,
  or bypass authorization because canonical idempotency and state live in PostgreSQL.

## Four-guardrail freeze

1. Data isolation introduces no customer-facing organizations, workspaces, or extra roles.
2. No feature flag can reactivate removed roles, portals, editor, Craft.js, Pinecone, or Chroma.
3. The payment boundary activates no legacy or unapproved provider.
4. Privacy/account export never contains a deployable Website and cannot satisfy an ExportPurchase.
