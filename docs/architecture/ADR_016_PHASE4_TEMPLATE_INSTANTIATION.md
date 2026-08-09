# ADR 016: Phase 4 owns Template instantiation and the multi-page Draft model

Status: accepted

Date: 2026-08-10
Authority: the user-approved “Phase 4 — Multi-page Website Document Model + Template Instantiation” amendment

## Context

The original phase boundary placed most Website creation work after the Template catalogue. The
authoritative Phase 4 amendment requires Template selection itself to create an independent Draft
Website, including the complete persisted page hierarchy. It explicitly forbids a business
questionnaire, plan selection, payment, publishing limits, collaboration, and a separate dashboard
per Website at this point.

## Decision

- Phase 4 exposes one authenticated command: `POST /api/v1/templates/{slug}/instantiate`.
- The command accepts no business name, business type, industry, Website name, plan, or subscription.
- A current `PUBLISHED` Template version is the only valid source.
- One `websites` row is created with one non-null `owner_user_id`, the exact source Template version,
  a non-user-entered display label, and status `DRAFT`.
- Every Template Page is copied into `website_pages` with a fresh UUID. Parent IDs are remapped in
  memory before the rows are flushed, so source IDs never become permanent Website Page IDs.
- Page content, SEO data, navigation visibility, order, and hierarchy are copied by value. A Website
  cannot mutate its Template source or another Website.
- Multiple Drafts per User are allowed. There is no Draft-count or page-count entitlement check.
- The User continues to use one portal. `/app/websites` lists Drafts; a per-Website dashboard and the
  editing/Page Manager UI remain Phase 5 work.

## Invariants

- `websites.owner_user_id` is non-null; no collaborator, team, seat, invite, co-owner, or shared
  permission tables are introduced.
- A composite self-reference `(parent_page_id, website_id) -> (id, website_id)` prevents
  cross-Website parents at the database boundary.
- A self-parent check plus the canonical server hierarchy walk rejects self-parenting, cycles, and
  depth beyond 12.
- A partial unique index permits exactly one stored home Page per Website; the application creates
  that home atomically and refuses a nested home. Home stores an empty slug and resolves to `/`.
- Sibling slugs are unique. `resolve_page_path` is the single path resolver for nested URLs.
- Ownership transfer is not implemented in Phase 4, but the direct current-owner field does not
  remove or preclude the separately audited transactional transfer workflow.

## Consequences

The Phase 4 schema contains two additive migrations: the Template platform and the owned
Website/Page model. Existing records are not rewritten or dropped. Phase 5 can build editor and
Page Manager commands on this persisted structure without changing the creation contract. Phase 7
remains responsible for plan eligibility, page limits at publish time, billing, and publishing.
