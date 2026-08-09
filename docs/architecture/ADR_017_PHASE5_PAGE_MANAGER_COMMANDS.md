# ADR 017: Phase 5 uses server-authoritative Page commands and generated navigation

Status: accepted

Date: 2026-08-11
Authority: the user-approved "Phase 5 - Page Manager + Hierarchical Website Map + Navigation" amendment

## Context

Phase 4 established one-owner Draft Websites, persisted Page hierarchy, and one canonical nested
path resolver. Phase 5 must expose that model to Users at 1, 30, and 100+ Page scale without adding
a blank-canvas builder, collaboration, plan gating, publishing, or a second Website dashboard.

Site structure and primary navigation cannot be the same concept: legal, campaign, and thank-you
Pages need stable paths without necessarily appearing in navigation. Parent deletion and path
changes also need explicit semantics so normal organization cannot silently lose descendants or
erase information needed by a later redirect system.

## Decision

- The editor route is `/app/websites/{website_id}/edit`; its primary Pages surface is a compact,
  scrollable, searchable, collapsible tree with keyboard navigation and contextual settings.
- FastAPI owns add, update/move, and confirmed delete commands. Commands lock the Website aggregate,
  require the current owner and `DRAFT` state, and validate the complete proposed hierarchy.
- Slugs are lowercase URL segments. Empty non-home slugs, unsupported characters, reserved root
  routes, duplicate siblings, self-parenting, cycles, excessive depth, and cross-Website parents are
  rejected server-side; matching client checks provide immediate feedback only.
- `show_in_navigation` is independent of Page existence. Navigation is a deterministic projection
  generated from persisted hierarchy, visibility, and ordering rather than manually maintained links.
- Reparenting and slug changes record old/new canonical paths for affected descendants in
  `website_page_path_changes`. Phase 7 may materialize redirects when publishing; Phase 5 does not.
- Delete requires `confirm: true` and the only Phase 5 child strategy is `PROMOTE`: direct children
  move to the deleted Page's parent and keep deterministic relative order. The command rejects any
  collision the promotion would create.
- Home stays at `/`, at the root, visible, active, and undeletable. Assigning a replacement home is
  outside this Phase 5 command set, so the exact-one-home invariant remains continuously true.
- A 500-Page technical ceiling guards memory and response size. It is not data-driven plan logic and
  does not prevent building the required 100+ Page Drafts.
- Drag-and-drop and a visual canvas are not added. Existing explicit parent/order controls cover Page
  organization without reintroducing arbitrary component placement.

## Consequences

Normal hierarchy changes immediately regenerate navigation and canonical paths from the same source
of truth. A hidden Page remains editable and routable. Parent deletion is predictable and auditable.
The additive path-history migration has no destructive backfill and preserves all existing Website
and Page rows. Content editing remains Phase 6; redirect activation, plan eligibility, publishing
limits, billing, and publishing remain Phase 7.

No collaborator, team, invite, presence, shared cursor, co-owner, or per-Website tenant-dashboard
architecture is introduced.
