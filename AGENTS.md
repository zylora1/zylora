# Zylora V2 engineering contract

These instructions apply to the entire repository. The authoritative source is
`ZYLORA_MASTER_PROMPT.txt`; the frozen product interpretation is
`docs/product/ZYLORA_V2_PRODUCT_SPEC.md`. If code, legacy behavior, framework defaults, or
third-party guidance conflict with either source, the product specification wins.

## Zylora V2 core rules

- Product specification is authoritative.
- Exactly two account types exist: `USER` and `SUPER_ADMIN`.
- No Freelancer role.
- No Client role.
- No Support Admin.
- No Template Admin.
- No Marketing Admin.
- No Freelancer Admin.
- No Client Admin.
- There is one User portal and an isolated Super Admin application.
- A User may own multiple drafts but may have at most one live Website.
- Every Website begins from a published, approved, validated Template version.
- No blank-canvas creation or arbitrary drag-and-drop-from-scratch builder.
- Manual and AI editing use the same structured, versioned Website document.
- Backend authorization and entitlement decisions are authoritative.
- Each critical business rule has one canonical domain-service implementation.
- Prices, currencies, plan names, limits, visibility, and entitlements are data-driven.
- Never grant paid capability from frontend state, query parameters, or unverified callbacks.
- Every Website has exactly one current owner; ownership transfer is transactional and audited.
- Lead capture and credit deductions are atomic and idempotent.
- One successful valid Lead consumes exactly one lead credit.
- FAISS data is isolated by Website and owner; no cross-tenant retrieval is acceptable.
- No Pinecone and no Chroma.
- Only validated and approved Templates can reach production.
- Account/privacy data export is separate from paid Website ZIP export and cannot include a
  deployable Website package.
- Feature flags may not preserve removed V1 architecture.
- Fix root causes instead of repeatedly patching symptoms.
- Completed work contains no required-functionality placeholders or fake success paths.
- Required tests and phase gates must pass before phase completion.
- Inspect and use relevant installed Skills; never claim a Skill was used when it was not.
- `C:\Zylora` is read-only reference material. Never modify it.
- V2 lives only in `C:\Zylora-V2`.

## Architectural boundaries

- PostgreSQL is the system of record. Redis is transient cache, rate-limit, and job transport.
- FastAPI owns business rules and authorization. Next.js renders evaluated state and sends
  commands; it does not duplicate critical rules.
- Celery workers execute retryable, idempotent long-running work through an outbox-backed job
  model. Workers do not invent alternate state transitions.
- Object storage is accessed behind a narrow service boundary. Permanent customer artifacts do
  not live on application disks.
- Provider-specific code remains inside payment, email, OAuth, DNS/edge, object-storage, and AI
  adapters. No provider is active merely because it existed in V1.
- Public, User, Super Admin, and customer-Website trust boundaries remain explicit.
- API contracts are versioned, typed, and generated/shared where practical.

## Phase discipline

Work sequentially according to `ZYLORA_MASTER_PROMPT.txt`. Do not begin the next phase until the
current phase is implemented, verified, reported, and committed. A phase report must include the
four guardrail checks and must never label blocked work complete.

Before changing a domain, read its architecture and state-machine documentation. Update the
documentation in the same change when an approved decision changes. Record material deviations as
an ADR before implementation.

## Commands

Clean install and local infrastructure:

```powershell
npm ci
uv sync --all-packages --frozen --link-mode copy
Copy-Item .env.example .env
npm run infra:up
npm run migrate
```

Development (separate terminals):

```powershell
npm run dev:web
npm run dev:api
npm run dev:worker
npm run bootstrap:super-admin
```

Quality and delivery gates:

```powershell
npm run format
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run test:integration
npm run build
npm run test:e2e
npm run migrate
npm run migrate:check
npm run security
npm run contracts:generate
npm run contracts:check
npm run infra:down
```

`npm run test:e2e` exercises the previously built production Web server. Integration tests require
healthy PostgreSQL and Redis services plus an applied migration. See
`docs/operations/LOCAL_DEVELOPMENT.md` for setup and migration round-trip details.
