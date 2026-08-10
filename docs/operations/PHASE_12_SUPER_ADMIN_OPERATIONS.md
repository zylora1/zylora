# Phase 12 — Super Admin operations

The Super Admin workspace is a separate, authenticated application surface. It is not a User portal
with an elevated menu: every request uses the `ADMIN_WEB` session audience and requires the sole active
`SUPER_ADMIN` identity.

## Connected operational reads

The portal now renders real PostgreSQL-backed operational projections:

- overview counts for Users, Websites, Drafts, live Websites, Templates, subscriptions, trusted
  payments, Leads, and active domains;
- measured platform page views and Leads from the Phase 11 daily rollups;
- bounded records for Websites, PlanPrice and PlanEntitlement rows, subscriptions, invoices, payments,
  Leads, Lead and AI credit state, domains, transactional email state, analytics rollups, audit events,
  export prices, and the zero-credit policy;
- user search and detail, including signup provider, verification/account state, owned Website and
  live-site state, commercial history, both credit accounts/ledgers, Leads, domains, and relevant audit
  activity;
- real API readiness probes for database, Redis, and production identity readiness. The console never
  substitutes a green status when a probe fails.

All collection responses are bounded to 100 records. The operational projection deliberately does not
return encrypted email bodies, provider secrets, raw payment webhook payloads, or raw visitor hashes.

## Sensitive operations and evidence

Existing Super Admin commands remain the canonical mutation paths:

- versioned ZIP export pricing;
- lead zero-credit policy and idempotent lead-credit adjustments;
- Template identity/version/asset operations;
- Template metadata, category/tag/featured order updates;
- validated publish, unpublish, deprecate, and restore lifecycle actions.

Commands require the isolated admin origin and CSRF token. They write an `AuditLog` event with actor,
target, reason, and correlation evidence. A Super Admin user-detail read is also audited because it
exposes private account and commercial state.

Template restore is intentionally constrained: only a deprecated version with a current successful
validation can return to `PUBLISHED`. Unpublish removes the current published pointer and returns the
Template to `DRAFT`; it does not leave a public catalogue pointer behind.

## Production verification

1. Bootstrap exactly one active Super Admin with the documented command.
2. Sign in through the isolated Admin route and verify `/api/v1/admin/health` shows observed checks.
3. Confirm that a User search and detail request writes `admin.user_viewed` to audit logs.
4. Create a Template version, validate and approve it, publish it, then verify that unpublish removes it
   from the public catalogue and restore requires current validation.
5. Configure ZIP export prices only in integer minor units. Do not store provider credentials in the
   portal, API response, logs, or repository.

No migration is needed for this phase: it projects the existing authoritative relational state.