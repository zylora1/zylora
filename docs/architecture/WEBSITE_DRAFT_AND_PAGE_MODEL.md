# Website Draft and Page model

This document is the implementation contract for Template-first Draft creation. ADR 016 records the
Phase 4 boundary change; the frozen product specification and its authoritative amendment remain
the product authority.

## Aggregate layout

`Website` is the stable project identity. It has exactly one current `owner_user_id`, one exact
`source_template_version_id`, a system-derived display label, lifecycle status, and timestamps.
Phase 4 creates only `DRAFT` Websites. There is deliberately no subscription, plan, price,
publishing limit, collaborator, or separate tenant-dashboard relation in this aggregate.

`WebsitePage` is the persisted site-map and content unit. Each Page stores:

- a Website-specific UUID and the source Template Page ID as provenance only;
- `website_id`, `parent_page_id`, name, segment slug, sort order, home flag, navigation visibility,
  and Draft/hidden/archive status;
- an independent structured component document and SEO data;
- created and updated timestamps.

Template documents accept up to 200 Pages, so 1-, 5-, 20-, 30-, and 100-page Templates can be
selected before a plan exists. The Template validator checks a single root home, same-document
parents, cycles, depth, schema, component registry, content limits, links, requirements, and assets.

## Atomic instantiation

The authenticated User command loads only an active Template with its current `PUBLISHED` version.
Within one database transaction it:

1. creates the owned Draft Website;
2. allocates a fresh UUID for every source Page;
3. remaps every parent reference through that UUID map;
4. deep-copies component and SEO documents;
5. inserts all Pages and verifies database constraints;
6. records `website.instantiated_from_template` in the immutable audit log;
7. commits only after the response site map can be resolved.

Failure rolls back the Website, all Pages, and the audit row together. Selecting the same Template
again creates another independent Draft and another independent Page-ID set.

## Hierarchy and canonical paths

The home Page has `parent_page_id = NULL`, `is_home = true`, and `slug = ''`; it resolves to `/`.
Non-home Pages have a non-empty segment slug. `resolve_page_path(page, page_map)` walks ancestors,
rejects cycles or excessive depth, and builds paths such as `/about/team` or
`/services/web-design`. Components and clients do not invent their own nested URL algorithms.

The composite foreign key includes `website_id`, preventing a Page in one Website from using a
parent in another Website even if an application bug bypasses service validation. A partial unique
index prevents a second home, and a normalized sibling index prevents duplicate segments under the
same parent.

## Deferred work

Phase 5 owns editor revisions, Page Manager commands, and the editor route. Phase 7 owns plan
eligibility, publishing page limits, commerce, and publish transitions. No Phase 4 command charges,
publishes, checks a plan, or asks for business profile data.
