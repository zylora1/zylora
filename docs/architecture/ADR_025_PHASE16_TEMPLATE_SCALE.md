# ADR-025: Phase 16 template-catalogue scale and quality gates

## Status

Accepted and implemented in Phase 16.

## Decision

Zylora scales its Template catalogue through a deterministic, reviewed catalogue generator rather
than through duplicate records, superficial name swaps, or unvalidated database imports. The
catalogue contains the existing three curated Templates plus 1,000 new Template candidates spanning
ten product categories, ten content archetypes, 50 reusable visual families built from ten
layout seeds and five treatments, and one-, two-, and three-page site maps. Each generated document uses the existing structured Template schema and
only
registered components.

The scale gate runs at the 50, 100, 250, 500, and 1,000-candidate milestones. It requires unique
slugs, names, and document checksums; broad category coverage; sufficient content and 40-60-family variation;
site-map variation; successful document validation; and no unsafe markup or unsubstantiated
Testimonial-style content. It is deliberately deterministic so a release can be reproduced and
reviewed without a model call or a hidden mutable source.

Production seeding remains an explicit administrative operation. It first runs the scale gates, then
uses `TemplateService` to create, validate, approve, and publish every missing Template in batches
of 50. It neither changes existing Templates nor shortcuts the published-and-approved lifecycle.
The public API stays cursor-paginated, and the gallery appends bounded pages on demand; a 1,000-item
catalogue is never rendered as one giant client-side grid.

## Consequences

- Every catalogue candidate follows the same schema validation and approval boundaries as a manually
  created Template.
- Family treatments use the registered code-native `MEDIA` component for original abstract visual
  compositions. They never fabricate `TemplateAsset` references; IMAGE/GALLERY remain reserved for
  approved, READY object-storage assets.
- Category filters are served from active categories that actually contain a current published
  Template, avoiding stale filter choices.
- The scale validation command is a release gate and reports every required milestone.
- Visual review must sample each category, content archetype, reusable family, and responsive
  breakpoint after seeding; a passing structural gate does not substitute for editorial review.
- The catalogue does not invent customer outcomes, testimonials, AI claims, or unsafe executable
  content merely to make the set appear larger.
