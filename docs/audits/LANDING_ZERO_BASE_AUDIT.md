# Landing zero-base audit and reference notes

Date: 2026-08-13

## Deprecated implementation removed

The prior homepage was rooted at `WorldHome` and imported two product-story components plus a shared `WorldPublicSite`. Its 1,400-line `world-public.module.css` combined hero, template carousel, editor mockup, pricing, FAQ, navigation, and footer rules; a second module held responsive/publishing stories. `rebuild.css` was a later global override sheet imported by the root layout and affected auth, portal, blog, contact, and public surfaces.

Removed rather than wrapped or restyled:

- `components/world-home.tsx`
- `components/world-product-stories.tsx`
- `components/world-product-stories.module.css`
- `components/world-public-site.tsx`
- `components/world-public.module.css`
- `app/rebuild.css` and its root import

No `LandingPageV2`, backup stylesheet, patch artifact, hidden carousel, or duplicate mobile homepage remains. The canonical tree is now `LandingPage` plus the narrowly interactive `LandingPrompt` and data-driven `LandingPricing`; all landing selectors live in `landing-page.module.css`.

## Shared boundaries preserved

- `globals.css`: global reset, brand primitive, authentication, Blog/contact, and common application states. No new landing selectors were added.
- `portal.css`: User/Super Admin shell and editor/page-manager surfaces.
- `PublicSite`, `PublicNavigation`, and `PublicFooter`: recreated as the one canonical shared public shell used by Templates, pricing, Journal, contact, legal, and not-found routes.
- `BrandMark`, Turnstile, pricing API, Template catalogue, auth routes, portal, editor, billing, and dashboard components remain functional dependencies rather than landing copies.
- Existing `motion` and Embla packages were not expanded; the new landing needs no additional dependency.

## Current reference analysis

Reviewed the current public structure and messaging of [Emergent](https://app.emergent.sh/landing/) and [Wix](https://www.wix.com/) on 2026-08-13. The implementation borrows only high-level lessons: decisive above-the-fold hierarchy, a central creation interaction, clear CTA contrast, deliberate long-form pacing, product proof before feature breadth, and responsive information grouping. It does not reuse their copy, source, branding, imagery, layout, CSS, illustrations, or animation concepts.

## Product claims

The page uses repository-backed facts only: 1,000+ prepared Template starting points, two creation methods, Template drafts, AI-assisted editing, server-authoritative publishing, custom domains, lead capture, ownership transfer, and eligible export. It includes no invented customer logos, user counts, ratings, uptime promises, SEO ranking guarantees, or fake testimonials. Use-case cards are scenarios, not endorsements.