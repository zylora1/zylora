# Zylora V2 test strategy

Status: **Frozen test architecture; executable suites arrive with their owning phases**

## Quality contract

A phase is complete only when its implementation, formatting, types, lint, unit/integration/E2E,
security, browser/visual, migration, build, and regression gates applicable to that phase pass. Tests
must exercise real rules and persistence; static fake data, frontend-only success, broad coverage
exclusions, and unimplemented handlers cannot satisfy acceptance.

The test pyramid favors fast domain tests, then PostgreSQL/Redis/object-store/provider integration,
then focused browser journeys. Concurrency and payment/security cases are first-class, not deferred
edge cases.

## Environments and determinism

- Unit tests have no network, clock, randomness, or provider dependency without injected fakes.
- Integration tests use real PostgreSQL and Redis containers/services, apply migrations from empty DB,
  and use isolated databases/namespaces per run.
- Object storage, email, payment, DNS, OAuth, AI, embedding, and malware ports have deterministic test
  adapters with explicit success/failure/timeout/duplicate/conflict controls.
- Provider contract tests run against official sandbox/emulator only when credentials are available in
  protected CI; lack of credentials does not produce fake production success.
- Time, UUID/idempotency generation, and job dispatch are injectable. Tests assert states/events, not
  sleep-based timing.
- Fixtures create only `USER` and `SUPER_ADMIN`; a guard test rejects any other account enum.

## Suite layout

```text
apps/api/tests/
  unit/            pure domain/service/state/validation tests
  integration/     PostgreSQL, Redis, storage and API transaction tests
  security/        authz, abuse and malicious-input regression tests
  contract/        OpenAPI/provider/worker event contracts
apps/worker/tests/ task idempotency, retry, checkpoint and failure tests
apps/web/src/      component/accessibility/state unit tests near source
apps/web/e2e/      Playwright customer/admin/public journeys
packages/*/tests/  schema, renderer, generated contract and design-token tests
tests/performance/ bounded load and regression scenarios
```

Coverage thresholds are ratchets per package and cannot exclude entire canonical domains. Critical
state machines/invariants require branch and mutation-oriented review even when aggregate line coverage
looks high.

## Unit coverage

Minimum canonical domain matrix:

- account enum, verification lifecycle, Argon2 session/auth epoch behavior, authorization policies;
- Website/document/Template/payment/subscription/export/domain/deployment/index state transitions and
  illegal transitions;
- Template schema, component registry, safe patches, migration, link/asset/SEO/responsive checks;
- Website requirements, every entitlement operator, four-plan validation, exact eligibility reasons,
  recommendation, and current subscription reuse;
- exact money/price snapshot and payment transition/reconciliation rules;
- ownership transfer validation and one-live-site reservation rules;
- Lead normalization/idempotency, zero-credit policies, ledger invariants and exactly `-1` capture;
- AI patch parse/allowlist/scope/schema/accessibility validation and cost limits;
- FAISS manifest/path containment/stable IDs/checksum/isolation filters;
- structured errors/redaction/audit serialization;
- account export versus paid Website ZIP manifest separation.

Property-based tests are appropriate for state transition sequences, entitlement boundary values,
money, patch operations/tree invariants, slug/domain normalization, archive paths, and idempotency.

## Integration coverage

Use the real database constraints and transaction isolation to test:

- signup/verification/login/reset/session revocation and Google callback transaction behavior;
- exactly one active Super Admin and only two account values;
- create Website only from published approved Template; exactly one current ownership row;
- concurrent transfers leave one owner and revoke old authorization;
- concurrent publishes/subdomain claims leave at most one live Website/unique hostname;
- Website version optimistic conflicts, autosave retry, restore, and immutable history;
- four-plan catalog atomic publication and historical price/subscription immutability;
- checkout/webhook/reconciliation across duplicates, replay, wrong amount/currency/purpose, reordered
  events, conflicting terminal states, and DB failure recovery;
- deployment outbox, worker retry, health failure preserving old live deployment, and rollback;
- domain verification/provisioning degraded/recovery paths;
- failed payment prevents ZIP job/artifact/download; verified payment generates one sanitized artifact;
- account export has separate schema/storage and cannot invoke ZIP generator;
- form/chat Lead capture commits one Lead, one ledger entry, notification outbox, and analytics event;
- duplicate/retry/concurrent Lead requests return one result and one credit deduction;
- FAISS build/query/delete/rebuild and malicious cross-Website manifest/query attempts;
- Template validation and publish transaction; stale validation cannot approve changed checksum;
- campaign audience snapshot/suppression/idempotent delivery; Blog scheduled publish;
- account deletion orchestration and retained/anonymized financial/audit records.

## API and contract tests

- OpenAPI snapshot diff and generated TypeScript client freshness.
- Request schemas reject authoritative fields such as owner, price, entitlement result, payment status,
  credit delta, filesystem/index path, or admin role.
- Every command checks authentication, CSRF/origin, authorization, state, expected version, and
  idempotency as applicable.
- Error codes/status/problem shapes remain stable and safe.
- Cursor pagination is bounded, signed, stable across filter/order, and cannot enumerate other Users.
- Worker event schemas are versioned and tolerate duplicate/late delivery safely.
- Provider adapter contract suites apply identical scenarios to test and selected production adapters.

## Mandatory Playwright journeys

The release suite covers the full master-spec journeys:

1. Landing → email signup → verification → Portal; Google success/cancel/deny/error; login/logout.
2. New User first-Website CTA → Template Gallery → preview devices/pages/interactions → select → Draft.
3. Manual edit and AI edit → autosave success/retry/conflict → version restore → responsive previews.
4. Draft → eligibility/all four plans/reasons/recommendation → existing subscription reuse/upgrade →
   verified payment → deployment → Zylora subdomain/custom domain → live Website.
5. Website A live + Website B Draft → publish B blocked → unpublish A → publish B succeeds.
6. Transfer validation → live route removal if needed → atomic transfer → old owner denied → recipient
   sees Website and follows domain/publish flow.
7. Export current admin price → failed/unverified payment blocks ZIP → verified payment → secure expiring
   download; privacy export cannot yield Website package.
8. Publish → chatbot provision/query → cross-Website retrieval attack rejected → chatbot/form Leads →
   duplicate retry consumes exactly one credit → notification and analytics.
9. Super Admin isolated login → plan/export price and entitlement catalog change → credit adjustment →
   Template validate/approve/publish/deprecate → manual email/campaign/Blog publish → audit/system health.

Journeys run with seeded deterministic test data, not mocked UI responses, at least on Chromium in CI;
release candidate adds supported browser matrix based on product decision.

## Browser and visual QA

For every major surface inspect actual running application at 1440, 1280, 1024, 768, and 390 pixels:

- console errors/warnings, failed requests, hydration, layout shift and overflow;
- loading, empty, success, error, retry, disabled, stale/conflict and session-expiry states;
- keyboard order, visible focus, skip links, dialogs, menus, traps/restoration, labels and live regions;
- every button/link/form/modal lifecycle, refresh, back/forward, deep links and interrupted jobs;
- realistic content extremes, zoom/reflow, reduced motion, touch targets and mobile navigation.

Store named screenshots/traces only as test artifacts with retention; do not commit noisy generated
output. Use semantic assertions before screenshot diffs. Visual baselines require human review for
intentional design changes.

Dedicated reviews evaluate public landing as product designer, conversion designer, and senior
frontend engineer, and ask whether any composition remains generic/AI-looking. Template batches are
automatically validated and visually sampled for repetition, typography, industry fit, hierarchy, and
mobile quality.

## Accessibility and SEO

- Automated axe-equivalent checks plus manual keyboard/screen-reader spot checks for critical paths.
- Semantic landmark/heading/name/label/contrast/focus/reduced-motion/target-size tests.
- Public pages: canonical, robots, sitemap, metadata, Open Graph, structured data, status codes, clean
  slugs and indexability. Portal/Admin/private previews assert `noindex`.
- robots.txt test ensures public Zylora is not blanket blocked.
- Lighthouse/Web Vitals checks investigate material regression without treating a perfect score as the
  sole goal.

## Security suite

Explicit tests include unauthorized User/Admin, IDOR/horizontal escalation across every owner-scoped
resource and collection, CSRF/CORS, XSS/HTML/CSS/script injection, open redirect/SSRF, brute force and
rate-limit alternate paths, upload polyglot/malware/oversize, ZIP traversal/symlink/bomb, malicious
Template/component, payment replay/duplicate/conflict, transfer/publish/credit races, secret leakage,
and cross-Website FAISS/prompt-injection attacks.

Protected CI runs dependency, license, secret, SAST and container/IaC scans. Findings are triaged by
exploitability and impact; P0/P1 blocks promotion.

## Migration and database gates

For every migration:

```text
empty PostgreSQL -> upgrade head -> schema/invariant assertions
previous release schema/data -> upgrade head -> application compatibility tests
head -> downgrade where declared safe -> upgrade again
```

Review locks/table scans, nullable-to-required staging, index creation, data backfill idempotency,
constraint validation, and rollback/forward-fix plan. Destructive changes use expand/migrate/contract,
never casual manual production DDL.

## Performance and resilience

Budgets are baselined after Phase 1/3 and ratcheted for public pages, Template search/preview, portal,
editor autosave, customer Websites, public Lead/chat/analytics APIs, publish queues, campaigns, and
FAISS query/build. Test bounded concurrency, payload limits, queue backpressure, cache misses, provider
timeouts, DB/Redis/storage outage, worker death/lease expiry, and retry storms.

No performance test may sacrifice tenant isolation or payment/credit correctness.

## Phase gates

| Phase | Additional required evidence |
| --- | --- |
| 0 | docs exist, links/format clean, invariants/state/data/API/security/design/ops consistent |
| 1 | clean install, lint/type/build/tests, empty migration, health, config failure, CI |
| 2 | complete auth/abuse/session/authz/security matrix |
| 3 | responsive/accessibility/empty-loading-error browser QA; no fake analytics |
| 4 | schema/registry/validator/catalog/admin and visual Template sample |
| 5 | ownership/live-site/create-from-approved-Template concurrency invariants |
| 6 | manual/AI/autosave/conflict/restore/responsive/SEO editor journeys |
| 7 | four-plan/requirements/eligibility/recommendation/billing/payment state |
| 8 | domain/deployment/health/rollback/failure/one-live concurrency |
| 9 | transfer race/revocation and export payment/security/bypass |
| 10 | FAISS isolation, unified Lead/ledger exactly-once under stress |
| 11–14 | real data, admin operations, campaign/Blog, public SEO/a11y/performance/visual |
| 15 | feature freeze and complete regression/security/browser/template/payment/concurrency |
| 16 | batch validation plus visual sampling; methodology fixes for repeated defects |
| 17 | release-candidate full matrix, restore/rollback/operations and P0/P1 zero |

## Defect policy

Failures record reproduction, expected/actual state, correlation IDs, severity, and canonical owner.
Repeated patterns stop feature work and trigger root-cause abstraction plus regression tests. Flaky
tests are production-signal defects: fix or quarantine only with owner, reason, expiry, and blocking
tracking; never silently rerun until green.
