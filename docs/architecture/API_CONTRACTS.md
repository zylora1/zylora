# Zylora V2 API contract freeze

Status: **Resource and behavior contract frozen; OpenAPI generated in implementation phases**

## Contract principles

- JSON REST endpoints live under `/api/v1`; breaking changes require a new version or a documented
  compatibility window.
- FastAPI/Pydantic schemas are the transport source of truth. CI exports OpenAPI and generates the
  TypeScript client in `packages/contracts`; handwritten duplicate response types are prohibited.
- JSON uses `snake_case` at the wire unless the generated-client strategy formally adopts one global
  transform. Dates are RFC 3339 UTC, IDs are opaque strings, and money is `{amount_minor, currency}`.
- Unknown request fields are rejected for commands. Responses may add fields compatibly.
- All state-changing browser requests use secure cookies, CSRF proof, explicit origin validation, and
  an idempotency key where the operation may be retried.
- Ownership, admin status, current price, entitlements, and payment status come from the authenticated
  server context, never request fields.

## Standard envelopes

Successful single-resource responses return the resource directly with a correlation header.
Collections use:

```json
{
  "items": [],
  "page": {
    "limit": 25,
    "next_cursor": null,
    "has_more": false
  }
}
```

Errors use `application/problem+json`:

```json
{
  "type": "https://docs.zylora.com/problems/domain-not-verified",
  "title": "Domain not verified",
  "status": 409,
  "code": "DOMAIN_NOT_VERIFIED",
  "detail": "Add the displayed CNAME record and check again.",
  "instance": "/api/v1/websites/…/publish",
  "correlation_id": "…",
  "field_errors": [],
  "retryable": true
}
```

The `code` is stable and machine-readable. `detail` is user-safe. Stack traces, SQL, provider secrets,
verification codes, internal paths, and raw payment evidence are never returned.

## Headers and concurrency

- `X-Correlation-ID`: accepted only after validation or generated server-side; echoed in response.
- `Idempotency-Key`: required for create-from-Template, publish, unpublish, transfer, checkout, Lead,
  export generation, campaign send, and other retryable commands.
- `If-Match`: required for mutable aggregate updates using a strong version ETag.
- `Retry-After`: returned for throttling, temporary lock, or known retry windows.
- Cursor pagination tokens are signed/opaque and bind filters/order to prevent tampering.

An idempotency key is scoped to actor + route + aggregate. Reuse with a different normalized request
fingerprint returns `409 IDEMPOTENCY_KEY_REUSED`.

## Authentication contracts

Public/user auth:

```text
POST /auth/email/signup
POST /auth/email/verify
POST /auth/email/resend
POST /auth/login
POST /auth/password-reset/request
POST /auth/password-reset/confirm
GET  /auth/google/start
GET  /auth/google/callback
POST /auth/logout
POST /auth/logout-all
GET  /auth/sessions
DELETE /auth/sessions/{session_id}
GET  /me
PATCH /me
POST /me/account-export
POST /me/deletion
DELETE /me/deletion
```

Admin auth uses an isolated audience and route/host:

```text
POST /admin/auth/login
POST /admin/auth/logout
GET  /admin/auth/sessions
DELETE /admin/auth/sessions/{session_id}
GET  /admin/me
```

Google start uses state, nonce, PKCE where supported, and a server-stored transaction. Callback
failure is atomic and redirects only to allowlisted internal targets. Cookie setting occurs only after
verified identity/account linking succeeds.

## Public catalog and content

```text
GET /templates?query=&category=&tag=&feature=&sort=&cursor=&limit=
GET /templates/{slug}
GET /templates/{slug}/versions/{version}/preview
GET /plans
GET /blog/posts?category=&tag=&cursor=&limit=
GET /blog/posts/{slug}
POST /contact
```

Template list queries are server-side, return only published/approved/validated versions, and include
capability/interaction metadata needed for preview. Preview returns a render descriptor or safe
preview URL, never arbitrary HTML from storage. `/plans` returns exactly four effective plans plus
prices and entitlement summaries from the current catalog.

## User Websites and versions

```text
GET    /websites?state=&query=&cursor=&limit=
POST   /websites                         create from template_version_id
GET    /websites/{website_id}
PATCH  /websites/{website_id}
DELETE /websites/{website_id}
POST   /websites/{website_id}/duplicate
GET    /websites/{website_id}/versions
GET    /websites/{website_id}/versions/{version_id}
POST   /websites/{website_id}/versions/{version_id}/restore
POST   /websites/{website_id}/validate
POST   /websites/{website_id}/ready
```

Creation accepts only the selected Template version and optional safe display name; industry/business
questionnaire fields are not required. The server resolves current User as owner and creates initial
ownership/version atomically.

## Editing and AI

```text
POST /websites/{website_id}/patches
POST /websites/{website_id}/ai-edits/plan
POST /websites/{website_id}/ai-edits/{operation_id}/apply
GET  /websites/{website_id}/edit-operations/{operation_id}
```

Manual patch request contains `base_version_id`, ordered typed operations, and client edit ID. AI plan
contains natural-language instruction, scope, base version, and optional selected component paths. AI
plan response is a preview of typed operations, explanations, usage estimate, warnings, and operation
ID. Apply reauthorizes and revalidates against current base; it never accepts arbitrary model output
from the client.

Conflict response `409 VERSION_CONFLICT` includes current version ID and safe rebase guidance. Patch
responses include saved state, new version, checksum, validation results, and correlation ID.

## Publish, plans, domains, and deployments

```text
GET  /websites/{website_id}/requirements
GET  /websites/{website_id}/publish-evaluation
POST /websites/{website_id}/publish
POST /websites/{website_id}/unpublish
GET  /websites/{website_id}/deployments
GET  /websites/{website_id}/deployments/{deployment_id}
POST /websites/{website_id}/deployments/{deployment_id}/retry
POST /websites/{website_id}/deployments/{deployment_id}/rollback
GET  /domains?website_id=&cursor=&limit=
POST /websites/{website_id}/domains/subdomain
POST /websites/{website_id}/domains/custom
POST /domains/{domain_id}/verify
DELETE /domains/{domain_id}
```

Publish request selects a domain ID and, when needed, a plan/checkout result reference. The API ignores
client eligibility flags and re-evaluates current state. Success is `202` with a Deployment resource,
not `PUBLISHED`. Clients poll or subscribe to bounded status updates.

Evaluation returns all four plans with `eligible`, stable reasons, current-subscription reuse, and
recommended plan plus explanation. It contains an expiry and input versions for display only.

## Subscription, invoices, and payment

```text
GET  /billing/subscription
POST /billing/subscription/checkouts
POST /billing/subscription/cancel
GET  /billing/invoices?cursor=&limit=
GET  /billing/invoices/{invoice_id}
GET  /billing/payments?cursor=&limit=
POST /billing/payments/{payment_id}/reconcile
POST /webhooks/payments/{provider}
```

Checkout requests identify the selected plan/price ID; server resolves amount/currency/purpose and
creates local Payment first. Webhook endpoints use the raw body, provider-specific signature headers,
strict size limits, replay detection, and always safe response behavior. User reconciliation is rate
limited and cannot override trusted provider state.

## Transfer and export

```text
POST /websites/{website_id}/transfers/validate
POST /websites/{website_id}/transfers
GET  /websites/{website_id}/transfers/{transfer_id}
POST /websites/{website_id}/exports
GET  /website-exports/{purchase_id}
POST /website-exports/{purchase_id}/checkout
POST /website-exports/{purchase_id}/generate
GET  /website-exports/{purchase_id}/download
```

Transfer request contains recipient email and confirmation version, never a target role/tenant.
Validation does not change ownership. Completion may be asynchronous for a live Website, but the
ownership commit remains atomic.

Export creation snapshots current admin price and exact Website version. `generate` returns `409` if
trusted payment is not paid. Download returns a short-lived redirect/stream only after current owner
authorization and `READY` artifact checks. Account export endpoints live under `/me` and share no
purchase/artifact code paths.

## Leads, credits, chatbot, analytics

Owner endpoints:

```text
GET   /leads?website_id=&source=&status=&query=&from=&to=&cursor=&limit=
GET   /leads/{lead_id}
PATCH /leads/{lead_id}
GET   /credits/balance
GET   /credits/ledger?cursor=&limit=
GET   /analytics/overview?website_id=&from=&to=
GET   /analytics/timeseries?website_id=&metric=&from=&to=&interval=
GET   /chatbots?website_id=
GET   /chatbots/{chatbot_id}/status
POST  /chatbots/{chatbot_id}/reindex
```

Narrow public Website endpoints:

```text
POST /public/sites/{site_token}/leads
POST /public/sites/{site_token}/chat/conversations
POST /public/sites/{site_token}/chat/conversations/{conversation_id}/messages
POST /public/sites/{site_token}/analytics/events
```

The server resolves Website from an opaque rotating site token and validated Host mapping. It never
accepts `owner_user_id`, index path, arbitrary Website ID, credit amount, or notification recipient.
Lead endpoint requires an idempotency key and returns the same result for a safe duplicate. Chat
responses include citations to same-Website content descriptors, not internal filesystem paths.

## Notifications and settings

```text
GET  /notifications?unread=&cursor=&limit=
POST /notifications/{notification_id}/read
POST /notifications/read-all
GET  /settings/security
PATCH /settings/profile
PATCH /settings/notifications
GET  /settings/marketing-consent
PATCH /settings/marketing-consent
```

## Super Admin contracts

Every endpoint below requires the isolated admin audience, `SUPER_ADMIN`, CSRF/origin validation for
commands, a reason for high-impact mutations, and audit logging:

```text
GET/PATCH /admin/users...
GET       /admin/websites...
GET/PATCH /admin/templates...
POST      /admin/templates/{id}/versions/{id}/validate
POST      /admin/templates/{id}/versions/{id}/approve
POST      /admin/templates/{id}/versions/{id}/publish
POST      /admin/templates/{id}/versions/{id}/deprecate
GET/POST  /admin/plan-catalogs...
POST      /admin/plan-catalogs/{id}/publish
GET/POST  /admin/export-pricing...
GET       /admin/subscriptions
GET       /admin/invoices
GET       /admin/payments
POST      /admin/payments/{id}/reconcile
GET       /admin/credits/accounts
POST      /admin/credits/adjustments
GET       /admin/leads
GET       /admin/domains
GET       /admin/analytics
POST      /admin/emails
GET/POST  /admin/campaigns...
POST      /admin/campaigns/{id}/send
GET/POST  /admin/blog/posts...
POST      /admin/blog/posts/{id}/publish
GET       /admin/system-health
GET       /admin/audit-logs
GET/POST  /admin/platform-settings...
```

Large collections use cursor pagination and server-side filter/sort allowlists. Bulk commands have
preview/dry validation plus explicit confirmation and per-item results; they do not silently partially
succeed.

## Health and internal contracts

```text
GET /liveness
GET /readiness
GET /version
POST /internal/outbox/dispatch       worker/service credentials only
POST /internal/jobs/{job_id}/...     worker/service credentials only
```

`/liveness` proves process responsiveness. `/readiness` checks mandatory DB connectivity and migration
compatibility, reports Redis/optional provider degradation without leaking configuration, and returns
non-ready only when the instance cannot safely serve its declared role. Internal endpoints use mTLS
or rotated service credentials plus network controls and are never browser-accessible.

## Authorization matrix

| Resource/action | Anonymous | USER | SUPER_ADMIN |
| --- | --- | --- | --- |
| Public content/catalog | read | read | read |
| Own Websites/Leads/domains | no | current owner only | audited operations read/write |
| Other User resources | no | no | audited support/operations scope |
| Publish/transfer/export | no | current owner + rules | no impersonated shortcut |
| Plan catalog/pricing mutation | no | no | yes, audited |
| Payment webhook | signed provider only | no | no |
| Public Lead/chat/analytics | scoped site token + controls | same public contract | same public contract |
| Account privacy export | no | own account | separate audited admin process |

Super Admin does not bypass payment or ownership state by pretending to be a User. Exceptional
correction commands are explicit, reasoned, audited operations with domain validation.

## Contract verification

CI must fail on:

- breaking OpenAPI changes without version/approval;
- generated TypeScript client drift;
- undocumented error codes or transitions;
- command schemas that accept owner, price, entitlement result, payment success, or filesystem path;
- collection endpoints without bounded pagination;
- missing authorization and idempotency test cases for state-changing routes.
