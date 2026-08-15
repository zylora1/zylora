# Zylora final pre-launch audit

**Audit date:** 2026-08-12  
**Decision:** **RELEASE CANDIDATE BLOCKED**

## Executive summary

The production build, static quality gates, dependency/security gate, web unit suite, API/worker unit suite, and complete Chromium E2E suite pass. This audit found and fixed accessibility contrast defects, a public-route outage hang, an ambiguous password field label, CSP/hydration incompatibility, and mobile tablet-preview fidelity.

The release candidate is blocked solely because this workstation cannot start Docker Desktop's Linux engine. PostgreSQL and Redis are therefore unavailable, so clean-database migration/round-trip, database-backed integration tests, live authorization abuse checks, and bounded live rate-limit verification cannot be certified. No known Critical or High security defect was found in the checked source and automated evidence.

This report covers an already-dirty worktree and does not create a commit or discard unrelated work.

## Automated test results

| Gate | Result | Evidence |
| --- | --- | --- |
| Formatting | PASS | `npm run format:check`: Prettier clean; 176 Python files formatted |
| Lint | PASS | `npm run lint`: ESLint and Ruff clean |
| Type checking | PASS | `npm run typecheck`: TypeScript clean; mypy clean across 123 Python source files |
| Web unit tests | PASS | 29 files, 72 tests |
| API + worker unit tests | PASS | 219 tests collected and passed with `--no-cov` |
| Migration metadata | PASS | `npm run migrate:check` |
| API contract freshness | PASS | `npm run contracts:check` |
| Template contract + scale checks | PASS | Contract check plus 50/100/250/500/1,000-template batches |
| Security/dependency gate | PASS | `npm run security`: npm audit 0 vulnerabilities; pip-audit no known vulnerabilities; architecture and Cloudflare checks pass |
| Production build | PASS | Next.js production build and API/worker source distributions build |
| Full Playwright E2E | PASS | 36 passed, 8 intentional duplicate-project skips |
| Database integration tests | BLOCKED | `npm run test:integration` timed out while migrations waited for unavailable PostgreSQL |

## Coverage

Frontend V8 coverage from `npm run test:web`:

| Statements | Branches | Functions | Lines |
| ---: | ---: | ---: | ---: |
| 91.81% (213/232) | 86.63% (188/217) | 91.93% (57/62) | 93.68% (193/206) |

The database-dependent Python coverage gate cannot be evaluated without the integration suite. A direct unit-only coverage attempt is not treated as a pass because it measures 63.83% against the repository's 90% aggregate threshold when integration tests are excluded.

## Production build

`npm run build` passed. The web production build emitted all expected public, User portal, and isolated Super Admin routes. API and worker sdist/wheel artifacts were also built successfully.

The root layout is deliberately dynamic so every response can receive the unique nonce required by the strict CSP. This is a security/caching trade-off to monitor in production performance telemetry.

## Visual and responsive QA

Playwright executed full-page screenshot, horizontal-overflow, keyboard, console/network, and Axe checks at:

- 360x800, 390x844, 430x932, 768x1024
- 1024x768, 1280x800, 1440x900, 1920x1080

Coverage includes landing, public templates/detail/preview, contact, login/recovery/verification paths, User portal, 100-page Page Manager, AI editor, pricing/eligibility, and Super Admin console. Desktop tests explicitly set mobile/tablet viewports; duplicate mobile-project variants of those same viewport loops are intentionally skipped. Other mobile flows pass independently.

### UI/UX issues found and fixed

1. Public muted preview labels and an accent label failed WCAG AA contrast. Their shared colors were darkened/lightened to compliant values.
2. The Super Admin sidebar wordmark inherited a second opacity, dropping it below WCAG AA contrast. The inherited opacity is now neutralized.
3. The password reveal button made a partial `Password` accessible-name query ambiguous. The password input now has an explicit label/id relationship and the reveal control retains its own accessible name.
4. A nonce CSP with statically rendered Next scripts blocked hydration. The layout now renders dynamically, passing strict nonce CSP without `unsafe-eval` or a broad script source.
5. Sitemap enrichment and template/blog metadata could wait indefinitely when the internal API was unreachable. Public enrichment now has a 2.5-second abort timeout and safe fallback; the stable sitemap and public route remain available.
6. Mobile preview CSS constrained the requested 768px tablet iframe to the device width, so the tablet selector did not show a tablet canvas. The scrollable preview stage now preserves the selected canvas width without causing page-level overflow.
7. The loading-state test was timing-dependent. It now uses a controlled deferred API response and verifies both loading and fail-closed session states deterministically.

## Accessibility

- Axe WCAG 2 A/AA/2.1 AA assertions pass on public responsive breakpoints and User/Super Admin viewport audits.
- Keyboard checks cover skip links, responsive navigation opening/closing, focus visibility, and accessible auth controls.
- Error, loading, and session-ended states are exposed with semantic status/alert roles.
- The template preview iframe is sandboxed with an empty `sandbox` attribute and verifies inaccessible cookie/storage behavior.

## Security audit

### Authentication, sessions, and Turnstile

Source and unit-test review confirms server-side Turnstile Siteverify validates success, action, hostname, replay/failure conditions, and fails closed. Protected flows include signup, verification/resend, User login, Google OAuth start, password recovery, and Super Admin login. Tokens/secrets are not logged or returned to the client. Google OAuth, email delivery, and real Turnstile production credentials remain external smoke checks.

### Authorization, tenant isolation, and Super Admin

The checked architecture uses server-side ownership/service boundaries. E2E validates that the User host does not expose Super Admin routes and that the isolated admin host presents its own experience. Template preview tests validate sandbox/cookie isolation; Page Manager and AI E2E cover large-tree, plan-free draft and scoped edit flows. Database-backed IDOR/BOLA mutation attempts remain blocked by the missing local stack and must be run before release.

### Input validation, XSS, CSRF, CORS, and APIs

Review found typed API boundaries, controlled template rendering/sanitization, no broad CORS-with-credentials configuration, and origin/CSRF protections on protected commands. Blog HTML rendering escapes untrusted source before rendering. No source-based SQL/command/path traversal issue was found. Database-backed malicious-payload requests still require the integration environment.

### Headers, cache, and information disclosure

Web responses use a nonce-based CSP with `strict-dynamic`, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, strict referrer policy, restrictive permissions policy, and production HSTS. Direct API responses now receive equivalent browser hardening; `/api/v1/` responses are `private, no-store` and non-indexable. API header middleware has dedicated unit coverage.

### Billing, domains, publishing, AI, exports, and leads

Existing E2E/unit coverage confirms server-driven pricing, plan eligibility at publish time, 30-page draft editing before a plan decision, User/Super Admin separation, AI revision/credit path behavior, and preview sandboxing. The payment provider is not exercised with real money; DNS, object storage, email, WhatsApp, and provider webhooks need configured staging/production credentials. Source review found no evidence of secrets in exported artifacts.

### Secrets and dependencies

The repository/worktree and visible history were scanned using available local checks without printing values. No matching committed credential material was found. `npm audit --audit-level=high` reported 0 vulnerabilities; `pip-audit --local --skip-editable` reported no known vulnerabilities. Semgrep, Bandit, Gitleaks, and Trivy were not installed and were not added solely for this audit.

## Rate-limit matrix

Cloudflare Terraform defines independent `cf.colo.id` + `ip.src` counters. The static configuration and project security check pass. Live 429/Retry-After behavior is **not verified** because no Cloudflare zone is connected from this local environment; no high-volume test was performed.

| Endpoint group | Identity / expected behavior | Static result | Live result |
| --- | --- | --- | --- |
| Auth + verification commands | colo + visitor IP; 10/min; 10-minute mitigation | PASS | BLOCKED |
| OAuth callback | colo + visitor IP; 20/min | PASS | BLOCKED |
| Public contact, leads, chatbot | colo + visitor IP; 20/min | PASS | BLOCKED |
| AI edit plans | colo + visitor IP; 10/min; 5-minute mitigation | PASS | BLOCKED |
| Template draft instantiate | colo + visitor IP; 10/min | PASS | BLOCKED |
| Template catalogue/preview reads | colo + visitor IP; 90/min | PASS | BLOCKED |
| Checkout snapshots | colo + visitor IP; 5/min | PASS | BLOCKED |
| Publish, unpublish, transfer | colo + visitor IP; 10/min | PASS | BLOCKED |
| Public plan catalogue | colo + visitor IP; 120/min | PASS | BLOCKED |
| General public API ceiling | colo + visitor IP; 120/min | PASS | BLOCKED |

## Browser, console, network, performance, and SEO

- Chromium is installed and passed the complete browser suite. Firefox/WebKit are not installed on this host.
- The in-app browser connection failed before use because of a host Windows sandbox ACL error. Playwright Chromium was the strongest available real-browser substitute.
- E2E console/network monitors pass for the audited flows. Next reported harmless destination-stream-closed messages during Playwright teardown after all tests passed; no test-page console/network assertion failed.
- Public metadata, canonical values, robots, sitemap, OpenGraph/Twitter metadata, and private-route exclusion are covered by source/E2E checks. Sitemap failure handling was hardened during this audit.
- No production RUM/LCP/CLS/INP telemetry is available locally. The dynamic CSP layout is a specific performance observation to measure after deployment.

## Known limitations and remaining issues

### Blockers

1. **Infrastructure / release evidence:** Docker Desktop Linux engine is not available (`//./pipe/dockerDesktopLinuxEngine` is missing). Start PostgreSQL/Redis with `npm run infra:up`, then run clean migration, downgrade/upgrade where supported, `npm run test:integration`, and the full Python coverage gate.
2. **Production edge/provider verification:** A deployed Cloudflare zone, provider credentials, and safe staging configuration are needed to verify edge 429 behavior, real Turnstile, OAuth, email, payment/webhook, DNS/domain, object storage, and WhatsApp flows.

### Non-blocking observations

- **Low:** Dynamic rendering is required for strict per-request CSP nonces; observe production performance metrics after deployment.
- **Low:** Firefox and WebKit were unavailable locally; run a focused cross-browser staging smoke test when those browsers are provisioned.

## Minimum human checks still required

1. Repair/start Docker Desktop, run the database migration round-trip and integration/full Python test gates.
2. Deploy to controlled staging with real non-production secrets; perform bounded Cloudflare rate-limit/Turnstile checks and inspect 429/Retry-After behavior.
3. Complete one real-but-safe provider smoke flow each for Google OAuth, verification email, payment webhook, domain verification, object storage/export, and WhatsApp notification.
4. Perform a short human visual review of the production landing, auth, editor, publish, and Super Admin surfaces in Chromium plus Firefox/WebKit if available.

## Release decision

**RELEASE CANDIDATE BLOCKED**

The code-quality, production-build, browser, accessibility, and available security evidence is green, with no known Critical or High finding. A PASS would be inaccurate until database-backed integration/migration checks and live edge rate-limit/provider verification are completed.
