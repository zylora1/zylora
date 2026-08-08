# Phase 0 — Product and architecture freeze

## Status

**PASS**

Phase 0 is documentation-only. No feature implementation was started.

## Implemented

- Preserved the complete master specification in the new V2 repository.
- Inspected V1 strictly read-only for stack, provider, operational, testing, and architecture lessons.
- Created repository-wide `AGENTS.md` with permanent product/engineering invariants.
- Froze product actors, journeys, acceptance invariants, and four guardrails.
- Defined monorepo/runtime boundaries, canonical services, provider ports, configuration, jobs/outbox,
  object storage, and FAISS isolation.
- Designed the relational model, DB constraints, ownership and one-live-site enforcement, retention,
  and concurrency recipes.
- Defined Website, Template, deployment, domain, ownership, payment, subscription, export, chatbot,
  notification, campaign, Blog, and job state machines.
- Defined versioned API behavior, error/idempotency/concurrency contracts, endpoint inventory, and
  authorization matrix.
- Defined the structured Template/Website schema, component registry, safe patch vocabulary,
  migrations, validator, and paid export contract.
- Defined four-plan requirement/entitlement/recommendation behavior and an unselected payment-provider
  boundary that cannot resurrect V1.
- Defined authentication, authorization, tenant isolation, content/build/upload/ZIP/payment/FAISS
  security controls and security tests.
- Defined test pyramid, mandatory journeys, browser/visual/accessibility/security/migration gates.
- Defined Zylora brand, token system, landing narrative, UI/component/motion/responsive principles.
- Defined environment separation, CI/CD, migration/release/rollback, observability and disaster
  recovery.

## Architectural decisions

- Modular monolith: Next.js Web, FastAPI API, Celery worker, PostgreSQL authority, Redis transient
  transport/cache, S3-compatible object storage, and Website-scoped FAISS artifacts.
- Exactly two account types and no organization/workspace customer model.
- Exactly one open ownership row per Website via partial unique index plus deferred constraint trigger.
- Maximum one live Website per User via `live_owner_user_id` partial unique index.
- Immutable Website/Template/catalog/deployment/commercial history with canonical transition services.
- Transactional outbox and idempotent workers for all external side effects.
- No production payment adapter until an explicit provider decision; V1 Razorpay code is not approval.
- Cloudflare for SaaS is the preferred domain/edge adapter behind a narrow port.
- Paid Website ZIP and account/privacy export are separate end-to-end capabilities.

## Skills / specialized capabilities used

- Repository and architecture inspection
  - Purpose: understand V1 integrations and failure patterns without copying or modifying V1.
  - Influence: retained provider boundaries, locking/idempotency, FAISS atomic artifacts, health and
    recovery patterns; rejected legacy roles/portals, broad coverage exclusions, and overlapping rules.
- Relational, security, API, design-system, QA, and operations modeling
  - Purpose: produce an internally consistent implementation contract before code.
  - Influence: database-enforceable invariants, explicit trust boundaries, deterministic state/contract
    behavior, and phase-specific gates.

No installed artifact Skill directly applied to a Markdown product/architecture freeze, so none was
claimed. The in-app browser capability is reserved for the required running-UI and browser QA phases.

## Tests

- Unit: not applicable; no runtime code exists in Phase 0.
- Integration: not applicable; no database/application foundation exists in Phase 0.
- E2E: not applicable; no UI/application exists in Phase 0.
- Documentation validation: PASS — 20 required/freeze files present, zero broken local Markdown links,
  zero placeholder implementation markers outside the preserved source prompt, zero forbidden legacy
  feature-flag names, and explicit role/four-plan/export/payment evidence found.
- V1 mutation check: PASS — V1 was read only; all created files are under `C:\Zylora-V2`.

## Typecheck

Not applicable — documentation-only phase.

## Lint

PASS — whitespace/patch checks and repository consistency scans pass.

## Build

Not applicable — application foundation begins in Phase 1.

## Migrations

Not applicable — logical model is frozen; Alembic foundation begins in Phase 1.

## Security

PASS for Phase 0 scope. Threat actors, trust zones, authentication/session/admin isolation, CSRF/CORS,
IDOR/tenant isolation, abuse/cost controls, uploads/Templates/build/ZIP, payment replay, FAISS isolation,
secrets, audit, privacy, supply chain, network controls, incident handling, and security gates are
defined.

## Visual / responsive QA

No UI exists to render in Phase 0. PASS for design-definition scope: brand direction, explicit tokens,
landing art direction, component/state rules, motion, accessibility, and required viewports are frozen.
Real browser automation and visual critique are mandatory from Phase 3 onward and for Template/public
surfaces in their owning phases.

## Known issues

No Phase 0 blocker. Planned later-phase selections are intentionally unresolved rather than guessed:

- production payment, email, object-storage, OAuth, AI/embedding, malware-scan, and telemetry adapters;
- exact supported dependency versions and executable install/test/build/migration commands;
- provider-specific deployment and disaster-recovery commands and measured RPO/RTO evidence.

Each selection has an explicit implementation gate and may not be replaced by fake success.

## Files / documentation

See the repository `README.md` architecture index. The freeze contains product, system, data, state,
API, Template, entitlement/payment, security, testing, seven design documents, environment/release,
observability, and disaster-recovery contracts.

## Guardrail check

1. Extra roles/orgs introduced? **NO**
2. Removed V1 architecture retained or feature-flagged? **NO**
3. Obsolete/unapproved payment provider activated? **NO**
4. Paid Website ZIP bypass created? **NO**

## Next phase

Phase 1 — Platform Foundation: implement the monorepo, pinned toolchains/dependencies, Web/API/worker,
PostgreSQL/Alembic, Redis/Celery, contracts, configuration/storage/logging/health, CI, `.env.example`,
and all clean-install/type/lint/test/migration/build gates before authentication work begins.
