# PHASE 2 - AUTH + ROLE MODEL

## Status

**PASS**

Phase 2 is implemented and every required executable gate passes. Cloudflare Turnstile and WAF are
the approved abuse boundary; the application and infrastructure configuration fail closed without
valid production configuration.

## Implemented

- Exactly two database account values: `USER` and `SUPER_ADMIN`, an at-most-one Super Admin
  constraint, one-to-one profile validation, single-use bootstrap command, and readiness requiring
  exactly one active profiled Super Admin.
- Email/password signup, Argon2id hashing/rehash, pending email verification, expiring single-use
  digested codes, safe resend generations, generic recovery responses, expiring single-use password
  reset, session revocation, and auth-epoch rotation.
- Google OIDC Authorization Code flow with state, nonce, PKCE S256, exact callback, minimal scopes,
  JWKS/claim validation, atomic account linking, provider-safe errors, and consumed cancellation.
- Opaque digested sessions; separate User/Admin audiences, cookies, CSRF namespaces, and hosts; expiry,
  revocation, device/session review, logout, logout-all, and individual revocation.
- PostgreSQL IP/account abuse budgets on every auth path with progressive cooldowns, generic responses,
  trusted-proxy-only visitor IPs, and immutable audit events.
- Cloudflare Turnstile explicit rendering on signup, login, verification/resend, password recovery,
  Google OAuth start, and Super Admin login. Siteverify sends only secret, token, visitor IP, and a
  random idempotency key; exact hostname/action is required. Missing, invalid, expired/replayed,
  wrong-host/action, malformed, timeout, and provider failure all fail closed. Tokens and secrets are
  never persisted or logged.
- Terraform-provisioned managed Turnstile widget, Cloudflare Managed and OWASP WAF rules, invalid
  method/scanner blocks, and rate limits for auth, verification, OAuth callbacks, public APIs,
  contact/Lead forms, and chatbot/Lead routes.
- Strict request schemas, problem+json errors, exact-origin/CSRF checks, generated OpenAPI/TypeScript
  contracts, SMTP delivery through Mailpit, and production configuration rejecting disabled/missing
  Turnstile, test keys, and hostname drift.
- Responsive User authentication/session surfaces and isolated Super Admin surfaces. Google OAuth and
  email verification are preserved; no Super Admin six-digit-code step was introduced.

## Cloudflare production actions

Application code and deployable Terraform are complete, but production operators must still:

1. Supply Cloudflare account/zone IDs and a minimum-privilege API token to the deployment secret
   manager, use encrypted remote Terraform state, review the plan, and apply `infra/cloudflare`.
2. Confirm the Cloudflare plan supports the selected Managed/OWASP WAF and advanced rate-limit rules,
   and tune reviewed false positives without bypassing server verification.
3. Proxy production User/Admin/API DNS through Cloudflare, configure origin TLS/firewall restrictions,
   and configure only the immediate trusted proxy in `TRUSTED_PROXY_IPS`.
4. Inject the Terraform site-key output as server runtime `TURNSTILE_SITE_KEY`; retrieve the widget
   secret directly into server-only `TURNSTILE_SECRET_KEY`; set exact User/Admin hostnames and enable
   Turnstile. No real credentials are committed.

These are production deployment inputs, not implementation blockers. Production application startup
rejects unsafe or incomplete values.

## Tests and gates

### Unit and integration

- Web: **31 passed** across 12 files; 94.15% statements, 90.32% branches, 94.73% functions, and 97.26%
  lines, including the security-critical Turnstile widget in enforced coverage.
- API/worker unified suite: **78 passed** against real PostgreSQL, Redis, and SMTP; 92.16% branch-aware
  total coverage (minimum 90%).
- Dedicated real-service integration gate: **9 passed**.
- Turnstile tests cover valid, missing, invalid, expired/duplicate-replayed, wrong hostname, wrong
  action, provider timeout/outage, minimum Siteverify payload, disabled development mode, exact route
  actions, production test-key rejection, and fail-closed configuration.

### E2E and responsive QA

- **6 passed** on desktop Chromium and Pixel 7 against the production Next server.
- The User auth E2E loads a deterministic Cloudflare script/config stub and proves the short-lived
  token reaches the login command; signup, safe errors, OAuth cancellation, Admin host isolation,
  response hardening, and overflow are covered.
- The required browser-control skill was followed. The in-app browser and direct screenshot viewer
  could not start because the host Windows ACL sandbox helper failed. Standalone Playwright completed
  successfully; this host-only tooling limitation is not an application defect.

### Static, build, migration, security, and infrastructure

- Format: **PASS** - Prettier and Ruff.
- Lint: **PASS** - ESLint zero warnings and Ruff.
- Typecheck: **PASS** - strict TypeScript and mypy across 42 source/script files.
- Build: **PASS** - optimized Next.js build and API/worker sdists/wheels.
- Migration: **PASS** - Alembic head `20260809_0002` and graph/schema validation.
- Contracts: **PASS** - regenerated OpenAPI/TypeScript contract and deterministic regeneration.
- Dependencies: **PASS** - npm audit 0 vulnerabilities; pip-audit no known dependency vulnerabilities.
- Architecture/security scanners: **PASS** - forbidden/removed architecture scan and Cloudflare control
  scan.
- Terraform: **PASS** - pinned Terraform 1.14.6/provider 5.22.0 `fmt -check`, `init -backend=false`, and
  `validate` using the official container.

## Architectural decisions

- PostgreSQL remains authoritative for identity, revocation, audit, and account/IP attempt budgets.
  Cloudflare edge controls complement rather than replace backend authorization and rate limiting.
- User/Admin audiences, cookies, host routing, and authorization remain isolated; Admin is not a
  navigation toggle and no extra role exists.
- ADR-015 records the approved Cloudflare provider/privacy boundary. Only minimum verification data
  leaves Zylora, and normal authenticated product interactions are not challenged.
- The Turnstile secret is server-only, omitted from API responses/Terraform outputs, and never exposed
  through `NEXT_PUBLIC_*` or frontend bundles.

## Files / documentation

- Server verification/config/routes/schemas: `apps/api/src/zylora_api/modules/auth`,
  `apps/api/src/zylora_api/api`, `apps/api/src/zylora_api/core/config.py`
- Browser widget and protected forms: `apps/web/src/components`, `apps/web/e2e/foundation.spec.ts`
- Provider infrastructure: `infra/cloudflare`
- Automated checks/tests: `apps/api/tests`, `apps/web/src`, `scripts/check_cloudflare_security.py`
- Environment/contracts/CI: `.env.example`, `packages/contracts`, `.github/workflows/quality.yml`
- Decision and operations: `docs/architecture/ADR_015_CLOUDFLARE_TURNSTILE_WAF.md`,
  `docs/operations/CLOUDFLARE_SECURITY.md`, `docs/architecture/SECURITY_MODEL.md`

## Guardrail check

1. Extra roles/organizations introduced? **NO**
2. Removed V1 architecture retained? **NO**
3. Obsolete payment provider activated? **NO**
4. Paid Website ZIP bypass created? **NO**

## Remaining blockers

None for Phase 2. Production Cloudflare credentials, DNS proxying, plan confirmation, and Terraform
apply are deployment actions requiring the operator's account and secret manager.

## Next phase

Phase 2 is complete. Phase 3 may begin only as a separate sequential change.
