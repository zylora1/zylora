# Public motion and SEO audit

Audit date: 2026-08-13

## Baseline architecture

- Next.js 16.3.0, React 19.2.8, CSS Modules plus shared CSS tokens.
- No Tailwind configuration.
- Installed interaction dependencies: Motion 13.1.0 and Embla 8.6.0.
- Existing landing motion was limited to CSS hover/placeholder animation and a shared MotionConfig.
- Existing responsive breakpoints primarily used 70rem, 54rem, and 42rem; browser tests covered 360,
  390, 430, 768, 1024, 1280, 1440, and 1920 pixels.
- Global and component-level reduced-motion rules already existed, but the landing had no meaningful
  scroll-driven sequence to reduce.

## SEO issue inventory

### Critical

No repository-side critical exposure was found. User, Super Admin, preview, and API surfaces were
already excluded from the sitemap and the principal application layouts were noindex.

### High — fixed

1. **Inherited root canonical risk:** the root canonical `/` could be inherited by routes without a
   local canonical. The root canonical was removed; indexable routes now own explicit canonicals.
2. **Environment crawl safety:** robots behavior did not distinguish an approved production hostname
   from preview/staging deployments. Indexing now fails closed unless explicitly enabled.
3. **Private-route response coverage:** several auth, unsubscribe, developer, and preview routes did
   not receive the same HTTP noindex policy as `/app` and `/admin`. The response-header matrix now
   covers all known private/internal surfaces.
4. **Motion architecture gap:** the landing had no scroll-linked product narrative despite its visual
   redesign. Shared semantic motion primitives and purposeful Website-generation/publishing scenes
   now replace isolated static demonstrations.

### Medium — fixed

1. Static sitemap entries used the deployment time as `lastModified`; those fabricated timestamps
   were removed.
2. Metadata and JSON-LD creation were repeated across routes; typed centralized helpers now enforce
   canonical/social/robots consistency and safe JSON-LD serialization.
3. The homepage lacked a truthful `SoftwareApplication` entity and visible FAQ structured data
   parity; both are now present without ratings, reviews, or invented price claims.
4. The public information architecture lacked dedicated pages for the two actual creation modes and
   the two strongest supported audiences. Five differentiated pages were added; speculative industry
   pages were deliberately not generated.
5. Footer links did not expose the complete public product/solution/legal hierarchy. Contextual public
   links now connect the homepage, creation paths, Templates, features, pricing, solutions, Journal,
   contact, and legal pages.

### Low / external

- Production www/non-www, HTTP/HTTPS, trailing-slash, CDN, and redirect behavior require the real edge
  configuration and hostname.
- Search Console ownership, sitemap submission, indexing confirmation, and production crawl data need
  domain credentials.
- Field LCP, CLS, and INP require production RUM. Repository browser checks can detect regressions but
  cannot substitute for field data.
- Genuine social-profile links were not found and were not invented. Hreflang was not added because no
  localized content exists.

## Route classification

### Indexable when production indexing is enabled

`/`, `/website-builder`, `/ai-website-builder`, `/features`, `/solutions/small-business`,
`/solutions/freelancers`, `/templates`, approved `/templates/{slug}`, `/pricing`, `/blog`, published
`/blog/{slug}`, `/contact`, `/privacy`, `/terms`, `/cookies`, and `/refunds`.

### Non-indexable and absent from sitemap

`/app/**`, `/admin/**`, `/api/**`, `/login`, `/signup`, `/verify-email`, `/forgot-password`,
`/reset-password`, `/unsubscribe`, `/health`, `/dev/**`, and `/templates/{slug}/preview`.

Template filters/sorts/query strings canonicalize to `/templates`. Only approved public Template API
records enrich the sitemap; responsive preview routes remain noindex. Customer Website previews,
drafts, and private records remain outside Zylora marketing SEO.

## Motion issue inventory

- Generic/static: product UI frames did not change with scroll and capabilities repeated a card-grid
  pattern.
- Jank risk: the shared navigation wrote React state directly from every scroll event.
- Reduced-motion gap: the prompt example rotated even for reduced-motion users.
- Mobile risk: a desktop-length pinning system would have produced excessive scroll travel on touch
  devices.

The implementation now uses Motion values outside React render state for scene transforms, one
requestAnimationFrame-throttled navigation listener, compositor properties, no duplicated smooth-scroll
loop, static mobile composition, and immediate reduced-motion content.
