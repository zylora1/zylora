# Phase 7 report: permanent pricing, entitlements, and publish eligibility

Status: **PASS**

Phase 7 is the permanent commercial and publication-eligibility layer. The implementation is
server-authoritative, data-driven, one-owner, and non-destructive. It does not start the Phase 8
deployment/domain workflow.

## Delivered

- Two immutable published monthly catalogs: India (INR) and International (USD). Prices are stored
  in minor units: Free 0/0, Basic 39900/900, Growth 99900/1900, and Business 199900/3900.
  Growth is the sole `MOST POPULAR` plan. No annual price or toggle is active.
- Exact plan entitlements: published pages 1/5/20/unlimited; custom domain and branding removal on
  paid plans; monthly AI credits 15/100/500/1500; WhatsApp notifications 0/150/750/2000; unlimited
  Lead persistence; and data-driven analytics/SEO tiers.
- Server-selected regional catalog. A persisted billing country wins; `CF-IPCountry` is accepted only
  when explicitly enabled behind a Cloudflare-only origin. Query/body region manipulation has no
  effect, and unknown country uses International pricing.
- Draft editing, preview, transfer, and save remain unlimited by publish-page limits. Publish
  evaluation recomputes page/domain requirements, returns all four plans and reasons, reuses a
  satisfying subscription, and recommends the lowest eligible plan.
- A row lock plus partial unique `live_owner_user_id` index allows one PUBLISHING/PUBLISHED/
  UNPUBLISHING Website per User. Phase 7 reserves `PUBLISHING` and emits an outbox intent; it never
  pretends that a route, TLS certificate, or deployment is already live.
- Immutable payment snapshots, verified-event idempotency, one subscription/invoice per event, and a
  test-only verifier that rejects production initialization. No unapproved provider can grant paid
  capability.
- Atomic audited ownership transfer closes the old ownership row, creates the recipient row, revokes
  old-owner access, and never creates collaboration. Ownership records cascade only if the Website
  itself is explicitly deleted; while a Website exists, history remains protected.
- AI allowances use the existing account/ledger and effective subscription period. WhatsApp quota
  exhaustion suppresses notification only; valid Leads are still stored exactly once.
- API-driven premium public pricing, portal billing, and per-Draft publish evaluation interfaces.
- Cloudflare rate limits for plan catalogue, checkout snapshot, publish/unpublish, and transfer while
  preserving Turnstile-free normal authenticated product interactions.

## Files and migration

The Phase 7 migration is
`apps/api/migrations/versions/20260813_0008_commerce_publish_entitlements.py`. It is additive and
backfills current Website ownership deterministically. It adds the catalog, plans, prices,
entitlements, subscriptions, payments, invoices, notification quota ledger, Lead store, ownership
history/transfers, billing country, and publish-reservation fields without removing page or revision
content.

Primary implementation areas are `apps/api/src/zylora_api/modules/commerce`,
`apps/api/src/zylora_api/api/commerce.py`, `apps/api/src/zylora_api/db/commerce_models.py`,
`apps/api/src/zylora_api/db/lead_models.py`, the Website/AI services, `apps/web/src/components`,
`apps/web/src/app/pricing`, `infra/cloudflare`, and generated API contracts.

## Verification

| Gate | Result |
| --- | --- |
| Backend + worker regression/coverage | 151 passed; 1 intentional skip; 90.16% total coverage |
| Dedicated integration suite | 19 passed, 1 intentional skip |
| Frontend regression/coverage | 52 passed; 93.20% statements, 88.32% branches, 90.90% functions, 95.55% lines |
| Playwright production-build E2E | 25 passed, 3 intentional mobile visual skips |
| Format, lint, typecheck | Passed |
| Production build | Passed (Web and Python packages) |
| API contract generation | Regenerated and committed with the new commerce routes/schemas |
| Template contracts | Passed |
| Security regression | npm audit clean; pip-audit clean; forbidden-architecture and Cloudflare checks passed |
| Migration | Main local upgrade passed; isolated upgrade → downgrade → upgrade and head check passed |
| Diff whitespace | Passed before commit |

## Guardrail check

1. Extra roles, organizations, or collaboration architecture introduced? **No.**
2. Removed V1 architecture retained or feature-flagged? **No.**
3. Obsolete or unapproved payment provider activated? **No.** The verifier is test-only and production
   checkout is unavailable.
4. Paid Website ZIP-export bypass created? **No.** Export behavior was not expanded in Phase 7.

## Production configuration still required

- Apply Cloudflare Terraform/OpenTofu with the pinned CLI, credentials, reviewed plan, and origin
  restricted to Cloudflare before enabling trusted `CF-IPCountry`.
- Select and approve a production payment provider, then implement its isolated adapter and webhook
  configuration. No secret, fake checkout, or test verifier is usable in production.
- Phase 8 must execute actual build, route/domain, TLS, health, traffic-switching, and terminal
  PUBLISHED/UNPUBLISHED transitions for the reserved publish intent.

## Remaining blockers

None for Phase 7. The local environment did not contain Terraform/OpenTofu, so deterministic
Cloudflare configuration validation was used; real infrastructure validation/apply remains a
deployment-environment operation and is documented in
`docs/operations/PHASE_7_COMMERCE_DEPLOYMENT.md`.

## Specialized capabilities

No additional Codex skill or external provider integration was used to alter Phase 7 behavior.
