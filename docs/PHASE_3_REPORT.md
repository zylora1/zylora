# PHASE 3 — DESIGN SYSTEM + PORTAL SHELLS

## STATUS

**PASS**

All Phase 3 acceptance criteria and repository gates pass. No P0/P1 defect or required Phase 3 work
remains.

## IMPLEMENTED

- A workspace-owned `@zylora/ui` package containing the frozen semantic design tokens and reusable
  Button, ActionLink, StatusBadge, Notice, PageHeader, EmptyState, ErrorState, and Skeleton patterns.
- The Zylora “digital atelier” visual direction: warm limestone/paper surfaces, botanical ink,
  restrained vermilion actions, scarce elevation, editorial display type, compact product type, one
  outline icon family, explicit focus, and reduced-motion behavior.
- A responsive authenticated User portal with stable Home, Websites, Templates, Leads, Analytics,
  Credits, Billing, Domains, Notifications, and Settings navigation.
- The first-time User experience: “Publish your first website,” an approved-Template CTA, and the
  Choose → Customize → Publish sequence with multiple-Draft/one-live-Website boundaries.
- A denser, isolated Super Admin shell with its own identity/session boundary and operational
  navigation. Its overview is evidence-led and refuses synthetic system, commercial, Website, or
  security summaries.
- Truthful future-section empty states. Analytics contains no fabricated charts, counts, percentages,
  or zero-value cards.
- Route and shell loading, error, retry, session-expiry, and skeleton states. Protected shell content
  is hidden until FastAPI verifies the existing session and fails closed when verification fails.
- Responsive persistent-sidebar/drawer behavior, Escape dismissal, one navigation DOM, visible focus,
  44-pixel controls, long-account-email truncation, and horizontal-overflow protection.
- Private `noindex, nofollow` and `private, no-store` response headers for User/Admin/auth surfaces,
  including Admin-host rewrites, while the public root remains indexable.

## ARCHITECTURAL DECISIONS

- `packages/ui` owns presentation tokens and framework-neutral primitives; FastAPI continues to own
  identity, authorization, entitlements, and business state.
- The Next.js shell evaluates server identity and renders commands/state. It does not invent Websites,
  analytics, billing, system health, or alternate backend transitions.
- User and Super Admin layouts share implementation mechanics but not session APIs, CSRF cookies,
  navigation, host exposure, logout destinations, or visual density.
- Phase 4 features were not pulled forward. Template and other future sections remain explicit empty
  states rather than placeholder functionality or fake success paths.
- Visual audit screenshots and traces are retained as Playwright artifacts and excluded from the
  commit.

## SKILLS / SPECIALIZED CAPABILITIES USED

- Sites building capability workflow: classified this as an existing multi-route application, mapped
  the frozen design sources into the shared system, and preserved the existing app-owned FastAPI
  authentication boundary. No Sites hosting manifest exists and Phase 3 did not authorize deployment.
- Browser-control workflow: attempted the required embedded-browser connection. The Windows sandbox
  could not apply its read ACLs, so the browser runtime could not initialize. The documented fallback
  used production Playwright, exact viewports, named artifacts, axe, semantic assertions, and direct
  rendered-image review through compact in-memory previews.
- Production Next.js, React Testing Library/Vitest, Playwright, axe-core, Lucide, FastAPI/Pytest,
  PostgreSQL, Redis, Docker Compose, Ruff, mypy, Alembic, and dependency/security scanners.

## TESTS

### Unit / component / regression

- Web: **39 passed in 16 files**.
- Web coverage: **93.62% statements, 88.71% branches, 90.90% functions, 96.06% lines**.
- API/worker: **78 passed** with **92.16% total coverage**.
- Coverage includes shared UI primitives, both shell identities, fail-closed identity behavior,
  navigation/drawer interaction, first-use CTA, no-fake-analytics copy, empty/loading/error states,
  route metadata, proxy isolation, and all Phase 2 authentication/security regressions.

### Integration

- Explicit real-service integration suite: **9 passed** after applying migrations.
- Full Python suite also ran all integration-marked tests against PostgreSQL, Redis, and Mailpit.

### E2E / accessibility / visual

- Production Playwright: **13 passed; 3 intentionally skipped duplicates**. The exact-viewport audits
  run once under desktop Chromium because they set their own 390/768/1024/1280/1440 viewports; standard
  journeys still pass in both desktop and Pixel 7 projects.
- Axe WCAG A/AA audit: **zero violations** on User and Super Admin shells at all five widths.
- Verified first-use CTA, stable navigation, mobile drawer, Escape dismissal, deep-link refresh,
  private response headers, Admin host isolation, truthful Analytics/Audit empty states, loading and
  fail-closed session states, no horizontal overflow, no console warnings/errors, and no real failed
  requests. Expected canceled Next.js RSC prefetches during full navigations are filtered explicitly.

## TYPECHECK

**PASS** — TypeScript and mypy report no issues.

## LINT

**PASS** — ESLint, Ruff formatting, Ruff lint, Prettier, and `git diff --check` pass.

## BUILD

**PASS** — Next.js generated 31 production pages/routes, including finite User/Admin section routes;
API and worker source distributions and wheels built successfully.

## MIGRATIONS

**PASS** — Alembic upgrade-to-head and migration-history validation pass. Phase 3 adds no schema
migration.

## SECURITY

- npm audit: **0 vulnerabilities**.
- Python dependency audit: **no known vulnerabilities**.
- Forbidden/removed architecture scan: **PASS**.
- Cloudflare Turnstile, managed WAF, custom WAF, and rate-limit control scan: **PASS**.
- User-host Admin routes return 404; Admin-host responses and all protected routes remain private and
  non-indexable. Provider secrets and authoritative state remain server-side.

## VISUAL / RESPONSIVE QA

- Inspected clean User Home at 390, 1024, and 1440; the 390 drawer; User Analytics on desktop/mobile;
  Admin Overview at 390, 1024, and 1440; the 390 Admin drawer; Admin Audit on desktop/mobile; and
  loading/session-ended states.
- Verified the required 390, 768, 1024, 1280, and 1440 widths programmatically and retained named
  screenshots for every User/Admin width plus both mobile drawers.
- Hierarchy, contrast, density, spacing, action priority, navigation labels, single-column reflow,
  long identity truncation, and state language remain coherent. No generic dashboard statistic cards,
  decorative gradients, glass effects, blank-canvas cues, clipped controls, or horizontal overflow
  were observed.
- Keyboard entry exposes the skip link and visible blue focus. Reduced motion preserves content while
  removing shell/skeleton animation.

## KNOWN ISSUES

- No Phase 3 blockers.
- The embedded app-browser runtime remains unavailable on this Windows host because its sandbox ACL
  helper fails before initialization. This did not block production-browser coverage or rendered-image
  review; the Playwright evidence is complete and green.
- Production Cloudflare dashboard activation remains a deployment operation documented in the Phase 2
  report. No real credentials were added.

## FILES / DOCUMENTATION

- Shared system: `packages/ui`, root workspaces/lockfile, Lucide and axe dependencies.
- Shells/routes: `apps/web/src/app/app`, `apps/web/src/app/admin/(portal)`, route loading/error files,
  and responsive portal CSS.
- Components: portal shell, navigation model, portal pages, route states, and shared brand mark.
- Tests: Web component/layout/proxy tests and production `portal.spec.ts` / `visual.spec.ts` journeys.
- Security/metadata: root metadata, scoped privacy headers, and Admin-host proxy responses.
- Documentation: this report, `docs/design/PHASE_3_IMPLEMENTATION.md`, and updated local development
  guidance.

## GUARDRAIL CHECK

1. Extra roles/orgs introduced? **NO**
2. Removed V1 architecture retained? **NO**
3. Obsolete payment provider activated? **NO**
4. Paid ZIP bypass created? **NO**

## NEXT PHASE

Phase 4 — Template Platform may begin only as a separate sequential change after this Phase 3 commit.
