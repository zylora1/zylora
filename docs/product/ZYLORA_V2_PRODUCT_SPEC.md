# Zylora V2 frozen product specification

Status: **Phase 0 frozen**
Authority: `ZYLORA_MASTER_PROMPT.txt`
Scope: product rules that implementation and acceptance tests must preserve

## Product promise

Zylora is a template-first Website platform. A User chooses an approved professional Template,
creates a private Draft, customizes the same structured document manually or with AI, and then takes
one of three primary actions: **Publish**, **Transfer**, or **Export ZIP**. Published Websites can use
a Zylora subdomain or verified custom domain and provide a Website-scoped FAISS chatbot, unified Lead
capture, analytics, notifications, and credit accounting.

## Actors

There are exactly two account types:

- `USER`: all customers, including people who happen to work as freelancers, agencies,
  consultants, developers, or business owners.
- `SUPER_ADMIN`: the single privileged operator of the Zylora platform.

The product has one unified User portal and one isolated Super Admin application. There are no
Freelancer, Client, Support Admin, Template Admin, Marketing Admin, organization, workspace, team,
or collaborator account types.

## Core User journey

1. A visitor signs up with Google or email/password plus a server-verified code.
2. A new User sees “Publish your first website,” not fake or empty analytics.
3. Create Website opens the Template Gallery directly.
4. The User previews desktop, tablet, and mobile behavior and chooses an approved Template.
5. Zylora creates a private Draft from the selected immutable Template version.
6. Manual and AI edits create validated revisions of one structured Website document.
7. The User previews, restores versions when necessary, and moves the Draft to Ready.
8. The User publishes, transfers to another existing User, or buys a Website ZIP export.
9. A published Website captures real events and unified Leads; one valid successful Lead consumes
   exactly one credit in the same idempotent transaction.

## Website rules

- Every Website starts from an approved, validated, published Template version.
- Blank-canvas creation and arbitrary freeform construction do not exist.
- Users may own multiple private Drafts.
- A User may have at most one published Website at any instant.
- Each Website has exactly one current owner and immutable ownership history.
- Ownership controls editing, publishing, domains, billing association, Leads, analytics, chatbot,
  transfer, and export.
- Drafts do not become separate dashboard applications.
- The three final actions remain Publish, Transfer, and Export ZIP.
- A Website is never marked published before a verified deployment passes its health check and the
  route is switched.
- A failed deployment keeps the last known-good version live.

## Template and editor rules

Templates are versioned structured documents, never uncontrolled arbitrary HTML. Their schema covers
metadata, theme tokens, pages, sections, components, responsive rules, editable properties,
interactions, animations, SEO defaults, assets, requirements, and a schema version.

Only validated and Super-Admin-approved Template versions are publicly selectable. Validation covers
schema, rendering, assets, links, responsive layouts, editor compatibility, accessibility, safety,
SEO, performance, build/runtime failures, and console errors.

Manual and AI editing both produce schema-valid changes to the Website document. AI returns a narrow
patch command set; Zylora authorizes and validates every patch before creating a new version. Rejected
patches never corrupt the current Draft. Advanced behavior is supported through registered,
parameterized components and interactions—not custom script injection.

## Publishing and domains

Publishing evaluates, server-side and in order: ownership, lifecycle transition, one-live-site rule,
Template/document validation, Website requirements, entitlements, billing, domain readiness,
immutable version creation, build, deployment, TLS/route configuration, health check, atomic traffic
switch, cache invalidation, analytics activation, and FAISS indexing.

Zylora subdomains are normalized, reserved-name checked, and unique. Custom domains are normalized,
verified through DNS ownership, provisioned through the configured edge adapter, issued TLS, and
activated only after health verification. Errors show exact DNS state and actionable recovery.

## Plans, pricing, and payments

The public catalog always presents exactly four subscription plans. Names, prices, currencies,
billing intervals, visibility, order, activation, entitlements, and limits are stored in versioned
backend data. The Website Requirement Service computes required capabilities; the Entitlement Service
returns eligibility and exact reasons; the Recommendation Service identifies the best eligible plan.

An existing subscription is reused when sufficient. Upgrade choices appear only when it is not.
Commercial records snapshot exact price, currency, interval, tax inputs, and entitlement/catalog
version so later price changes do not rewrite history.

No payment provider is approved by this Phase 0 specification. The eventual provider must be
explicitly selected. All payment activation requires server verification, signed webhooks,
idempotency, replay protection, reconciliation, immutable event evidence, and audited state changes.

## Transfer

Transfer accepts an existing Zylora User email, rejects self-transfer and invalid recipients, and
prevents concurrent operations. A published Website is safely removed from public routing before the
final transfer. The ownership change itself closes the prior ownership and creates the recipient's
ownership in one locked transaction. The old owner immediately loses authorization, the transfer is
audited, and the new owner uses the normal domain and publish flow.

## Export boundaries

Website ZIP export is a paid product. The server reads the current Super-Admin-controlled price,
creates an `ExportPurchase` with a price snapshot, verifies trusted payment state, generates a
sanitized archive in private storage, and grants short-lived authenticated access. The archive never
contains secrets, internal tokens, private platform code, or other Users' data.

Account/privacy export is an administrative portability function. It may contain profile, settings,
Website metadata, Leads, ledger records, and appropriate billing records. It uses separate services,
endpoints, artifacts, authorization, and audit events and never includes deployable Website source or
satisfies a paid `ExportPurchase`.

## Chatbot, Leads, and credits

Each successfully published Zylora-hosted Website gets a Website-scoped chatbot built only from that
published version. Source extraction, chunks, embeddings, manifests, and FAISS indexes are keyed to
the Website and current owner. Queries must provide the authorized Website identity and can never
search a global cross-Website index.

Website forms and chatbot capture feed one `LeadService` and normalized `Lead` model with source
attribution. A valid submission uses a caller-supplied idempotency key and one PostgreSQL transaction
to create the Lead, append exactly one `-1` ledger entry, enqueue notifications, and record an
analytics event. Retries return the original result. The centrally configured zero-credit policy
never silently discards contact information already submitted.

## Authentication and security experience

Google signup trusts only a verified provider callback and does not add a redundant Zylora OTP.
Email signup activates only after a throttled, expiring, single-use verification code succeeds.
Passwords use Argon2id. Password reset, session listing/revocation, secure HTTP-only cookies, CSRF,
session rotation, brute-force defense, suspicious-login logging, and safe recovery are mandatory.

Super Admin uses an isolated host or equivalent private route, a separate cookie namespace, strong
credentials, device/session management, WAF/rate limits, and immutable audit logging. Hiding UI never
substitutes for authorization.

## Public site and portal

Public pages include Home, Templates, Features, Pricing, Blog, Login, Sign Up, Contact, Privacy,
Terms, Cookie Policy, and Refund/Cancellation Policy. Marketing, Blog, and useful public Template
pages may be indexable. Private portal/admin pages are `noindex`; robots.txt must not block the whole
product.

User portal navigation is Home, Websites, Templates, Leads, Analytics, Credits, Billing, Domains,
Notifications, and Settings. Analytics become prominent only after meaningful real data exists.
Super Admin operations cover Users, Websites, Templates, plan/export pricing, entitlements,
subscriptions, invoices/payments, credits, Leads, domains, analytics, emails, campaigns, Blog/SEO,
health, audit logs, and configuration.

## Data and operational requirements

- PostgreSQL is the durable system of record; money uses integer minor units and explicit ISO 4217
  currency.
- External effects are outbox-backed, retryable, idempotent, observable, and bounded.
- Storage is private-by-default with validated uploads, unique keys, encryption, lifecycle rules, and
  signed access.
- Development, test, staging, and production use separate databases, Redis, credentials, buckets,
  secrets, and provider resources.
- Audit, payment, invoice, price, ownership, ledger, and deployment history are append-only or
  effective-dated.
- Data deletion follows an explicit lifecycle and retains only legally or operationally required
  records.
- Production has backup, restore, rollback, observability, rate-limit, WAF, dependency scanning,
  migration, and incident procedures.

## Acceptance invariants

An implementation is unacceptable if any of the following is false:

1. Only `USER` and `SUPER_ADMIN` account values are representable.
2. Tenant isolation exists without customer-facing organization/workspace roles.
3. Every Website begins from an approved Template version.
4. Every Website has exactly one current owner.
5. A User can never have two live Websites, including under concurrent publishes/transfers.
6. Publish, plan eligibility, and paid activation are server-authoritative.
7. The live plan catalog has exactly four data-driven plans.
8. Transfer is atomic and revokes the former owner.
9. ZIP generation/access is impossible before trusted payment verification.
10. Account export cannot produce or unlock a Website ZIP.
11. One successful Lead produces one Lead row and one `-1` ledger entry across retries.
12. FAISS retrieval cannot cross a Website boundary.
13. Only approved and validated Template versions are selectable.
14. Sensitive Super Admin actions are audited.
15. Removed V1 architecture cannot return through flags or compatibility layers.
