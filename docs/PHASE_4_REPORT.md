# PHASE 4 — MULTI-PAGE TEMPLATE PLATFORM

## STATUS

**PASS**

All Phase 4 acceptance criteria and repository gates pass. No required Phase 4 work or P0/P1 defect
remains.

## IMPLEMENTED

- Template-first Website creation: a User selects a published Template version and receives an
  independently editable Draft Website. The request has no business-name, industry, Website-name,
  subscription, payment, or plan-eligibility prerequisite.
- Multiple Draft Websites per User with one authoritative, non-null `owner_user_id` per Website and
  owner-only list/detail access. No collaborator, shared-permission, co-owner, or per-Website dashboard
  architecture was introduced.
- Immutable, versioned Template documents with categories/tags, schema validation, component-registry
  validation, deterministic checksums, validation records, approval/publish/deprecation lifecycle,
  safe asset ingestion, and public cursor-paginated catalogue/detail/preview APIs.
- A persisted multi-page Website model with fresh page identifiers, template provenance, parent-child
  hierarchy, sibling ordering, navigation visibility, status, independent content/SEO data, and
  timestamps.
- Atomic Template instantiation remaps Template-page parents to new Website-page IDs, deep-copies
  content, preserves the source Template, and supports Templates with at least 30 pages.
- Canonical nested-path resolution for `/`, `/about`, `/about/team`, and equivalent paths. The home
  page is a root page with an empty slug and resolves only to `/`.
- Database and service-layer protection against self-parenting, cycles, excessive nesting,
  cross-Website parents, duplicate sibling slugs, and invalid home-page states. A deferred PostgreSQL
  constraint trigger guarantees exactly one home page at transaction completion.
- Public and authenticated Template galleries, safe cookie-isolated responsive previews, Draft list,
  and an isolated Super Admin Template lifecycle surface. Full Page Manager/editor work remains Phase
  5 scope.
- Cloudflare catalogue and authenticated instantiation rate-limit rules, without adding unnecessary
  Turnstile friction to normal authenticated product interaction.

## MIGRATIONS

- `20260810_0003_template_platform.py` creates the Template catalogue, version, validation, asset,
  category, tag, and assignment schema.
- `20260810_0004_owned_website_pages.py` creates owned Draft Websites and their persisted page tree.
- `20260810_0005_exactly_one_home_page.py` adds the deferred exact-one-home invariant.
- The migrations are additive and deterministic. They do not drop valid Website/page data or remove
  legacy collaboration tables broadly. Alembic upgrade-to-head and linear-history verification pass.

## TEST RESULTS

### Quality / unit / integration

- `npm run quality`: **PASS**.
- Web: **42 passed in 18 files**.
- Web coverage: **93.62% statements, 88.71% branches, 90.90% functions, 96.06% lines**.
- API/worker: **99 passed** with **90.52% total coverage**, including integration-marked tests against
  PostgreSQL, Redis, and Mailpit.
- Generated OpenAPI and Template schema/component registry drift checks: **PASS**.
- Coverage includes Template lifecycle and validation, safe assets, cursor binding, 30-page
  instantiation, fresh/remapped IDs, source immutability, multiple Drafts, owner isolation, hierarchy
  rejection paths, exact-one-home enforcement, and request-contract behavior.

### E2E / accessibility / visual

- `npm run test:e2e`: **17 passed; 3 intentionally skipped duplicate mobile visual audits**.
- Phase 4 catalogue, detail, isolated preview, Draft creation/listing, and Super Admin lifecycle
  journeys pass in desktop Chromium and Pixel 7 projects.
- Axe WCAG A/AA checks report no violations on the covered Template/Draft surfaces.
- Production Playwright also preserved all Phase 1–3 authentication, host-isolation, portal,
  responsive, loading, session-expiry, and visual regressions.

## TYPECHECK / LINT / BUILD

- TypeScript and mypy: **PASS**.
- ESLint, Ruff lint/format, Prettier, `git diff --check`, and staged diff check: **PASS**.
- `npm run build`: **PASS**. Next.js generated 32 routes/pages; API and worker source distributions and
  wheels built successfully.

## SECURITY

- npm audit: **0 vulnerabilities**.
- Python dependency audit: **no known vulnerabilities**.
- Forbidden/removed architecture scan: **PASS**.
- Cloudflare Turnstile, managed WAF, custom WAF, and rate-limit control scan: **PASS**.
- Template preview content runs in a sandboxed iframe with an embedded deny-by-default CSP and no
  access to the parent origin's cookies or storage.
- Template writes require Super Admin authentication, exact-origin/JSON checks, CSRF validation,
  lifecycle reasons, and audit events. Draft access is owner-authorized server-side.

## VISUAL / RESPONSIVE QA

- Inspected the rendered responsive Template preview and Super Admin Template surface after automated
  desktop/mobile coverage.
- The embedded app-browser runtime could not initialize because the Windows sandbox ACL helper failed.
  Production Playwright, exact viewport assertions, Axe, captured artifacts, and direct rendered-image
  inspection supplied the fallback evidence.

## FILES / DOCUMENTATION

- API/domain: `apps/api/src/zylora_api/modules/templates`,
  `apps/api/src/zylora_api/modules/websites`, their routers, database models, and tests.
- Schema: the three Phase 4 Alembic migrations and generated OpenAPI contracts.
- Shared rendering contracts: `packages/template-schema` and its deterministic generator.
- Web: public/User/Super Admin Template routes, Draft listing, safe renderer/preview components, tests,
  and E2E coverage.
- Operations/security: Template seeding, Cloudflare rules/checks, and Template operations guidance.
- Architecture/testing: `ADR_016_PHASE4_TEMPLATE_INSTANTIATION.md`,
  `WEBSITE_DRAFT_AND_PAGE_MODEL.md`, `PHASE_4_TEMPLATE_PLATFORM.md`, and this report.

## PRODUCTION ACTIONS

- Apply the committed Cloudflare Terraform with the production account/zone identifiers and a
  least-privilege API token, then confirm the WAF/rate-limit rules are deployed and tuned from real
  traffic.
- Configure production Turnstile hostnames/keys and secrets as documented by Phase 2; no credentials
  are committed.
- Run the Template seed command with an active Super Admin identity in the target environment, then
  validate/approve/publish the curated versions through the audited lifecycle.

These are operator deployment actions, not Phase 4 implementation blockers.

## GUARDRAIL CHECK

1. Extra roles/organizations or collaboration architecture introduced? **NO**
2. Removed V1 architecture retained or feature-flagged? **NO**
3. Obsolete or unapproved payment provider activated? **NO**
4. Paid Website ZIP-export bypass created? **NO**

## REMAINING BLOCKERS

None for Phase 4.

## NEXT PHASE

Phase 4 is complete. Phase 5 may begin only as a separate sequential change; it was not started here.
