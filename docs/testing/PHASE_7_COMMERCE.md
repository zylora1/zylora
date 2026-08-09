# Phase 7 commerce and publish verification

Phase 7 verification covers the permanent India and International monthly catalogs, exact minor-unit
prices, Growth's single `MOST POPULAR` marker, all published-page/domain/branding/AI/WhatsApp/
analytics/SEO entitlements, and unlimited Lead persistence.

Integration tests create 1-, 5-, and 30-page Template-backed Drafts without a subscription. They
prove that page limits are absent from creation/editing, appear only in publish evaluation, recommend
Business for 30 pages, reuse an eligible Business subscription, and reserve only one live Website.
They also prove downgrade content preservation, atomic ownership transfer and authorization change,
151 persisted Basic Leads with notification 151 suppressed, exact price snapshots, idempotent trusted
payment processing, one invoice, and subscription-period AI allowances.

Security tests prove client/query/header region claims cannot select India unless trusted-edge country
handling is explicitly enabled; an established billing country cannot be overwritten by a request;
idempotency keys are mandatory and bounded; and the deterministic payment verifier rejects forged
signatures and all non-test environments.

Frontend tests prove the API-driven India prices, monthly-only display, Growth badge, disabled
placeholder checkout, current-subscription rendering, all-plan publish reasons, and existing-plan
reuse. E2E and manual checks cover the responsive public pricing surface and authenticated publish
evaluation.

Run:

```powershell
npm run migrate
uv run pytest apps/api/tests apps/worker/tests --run-integration --cov=zylora_api --cov=zylora_worker --cov-report=term-missing
npm run test:web
npm run test:e2e
npm run format:check
npm run lint
npm run typecheck
npm run build
npm run contracts:check
npm run templates:check
npm run security
npm run migrate:check
git diff --check
```

Migration verification additionally upgrades an isolated database to Phase 7, downgrades to Phase 6,
re-upgrades to Phase 7, and verifies deterministic catalog/backfill state.
