# ADR-027: Public motion and search system

## Status

Accepted for the Phase 14 public-experience hardening pass on 2026-08-13.

## Context

The existing rebuilt landing page had a strong authored visual direction, semantic copy, and public
Template/Blog boundaries, but the shared motion layer was limited to transition constants and generic
variants. The root metadata also supplied a canonical URL to descendants, route metadata was repeated,
the sitemap fabricated deployment-time modification dates for static pages, and crawler behavior did
not fail closed for unapproved hosts.

The public experience must add cinematic product storytelling without violating the frozen Zylora rule
that motion communicates causality and must not become scroll hijacking, arbitrary parallax, or
spectacle. Searchable copy must remain server-rendered semantic HTML rather than Canvas, WebGL, or
image-only content.

## Decision

### Motion

- Native browser scrolling remains authoritative. No Lenis-style interception is added.
- The already-installed Motion package owns scroll progress, spring smoothing, and compositor-only
  transforms. There is no second animation RAF loop.
- `StickyScene`, `ScrollLayer`, `ViewportProgress`, `MagneticLink`, and `SpotlightArticle` form the
  narrowly reusable public motion boundary.
- Three landing scenes communicate real product causality: prompt to generated Website, brief to
  verified build, and publish to domain/Lead workflow.
- Tablet/mobile replace long pinned choreography with a static content-first composition. Reduced
  motion removes pinning, autoplay placeholder rotation, pointer tracking, and scroll transforms while
  retaining all content and actions.
- Important text, links, headings, and process steps remain ordinary server-rendered HTML. Decorative
  product frames are DOM/CSS rather than essential Canvas/WebGL content.

### Search architecture

- `lib/seo.ts` is the canonical source for the public origin, entity identity, page metadata, private
  metadata, absolute URLs, and JSON-LD serialization.
- The root defines site-wide defaults but no inherited canonical. Every indexable route owns its
  canonical path.
- Production crawling is opt-in through `NEXT_PUBLIC_SEARCH_INDEXING_ENABLED=true`. An unset or false
  value disallows all crawling while retaining explicit private-path disallows for auditability.
- Private/auth/application/preview/internal routes receive both metadata-level noindex where a layout
  applies and `X-Robots-Tag: noindex, nofollow, noarchive` response headers.
- Static sitemap entries do not invent `lastModified` values. Blog publication dates are used only when
  supplied by the public API; Template entries do not fabricate dates.
- Only five differentiated search-intent routes are added: Website Builder, AI Website Builder,
  Features, Small Business, and Freelancers. No automated industry doorway set or speculative
  localization/hreflang is created.

## Consequences

- Cinematic behavior is centralized and testable without adding GSAP, Lenis, Rive, Three.js, or a
  second animation runtime.
- Public pages remain useful with JavaScript disabled because motion changes presentation rather than
  content availability.
- A deployment must explicitly set the production origin and enable indexing after hostname review.
- Search Console verification, sitemap submission, production crawl validation, and real Core Web
  Vitals remain external deployment work and cannot be claimed from the repository alone.
