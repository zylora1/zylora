# Public search release procedure

## Required production configuration

Set and verify:

```text
NEXT_PUBLIC_WEB_ORIGIN=https://<canonical-production-host>
NEXT_PUBLIC_SEARCH_INDEXING_ENABLED=true
```

All preview, local, and staging deployments must omit the indexing flag or set it to `false`. The
default is fail-closed and returns `Disallow: /`.

## Canonical and sitemap checks

1. Confirm the canonical production hostname resolves over HTTPS and choose one www/non-www variant.
2. Verify redirects from the non-canonical scheme/host go directly to the canonical URL with no chain.
3. Inspect `https://<host>/robots.txt` and confirm the sitemap points to
   `https://<host>/sitemap.xml`.
4. Crawl the sitemap and confirm every URL returns 200, has one H1, a self-referencing canonical,
   a distinct title/description, and no noindex directive.
5. Confirm `/app`, `/admin`, auth, preview, developer, unsubscribe, health, and API routes are absent
   from the sitemap and return an `X-Robots-Tag` noindex header where routed through Next.js.
6. Confirm unknown routes return HTTP 404 rather than a branded 200 response.

## Search Console actions requiring real ownership

- Verify the canonical production domain in Google Search Console.
- Submit `https://<host>/sitemap.xml`.
- Inspect representative homepage, creation-path, solution, Template, and Journal URLs.
- Monitor Page Indexing, Core Web Vitals, HTTPS, rich-result, and crawl-stat reports after deployment.
- Validate Organization, WebSite, SoftwareApplication, BreadcrumbList, FAQPage, and Article JSON-LD
  against the production HTML. Do not claim indexing until Search Console reports it.

## Motion and performance release checks

- Inspect the homepage at 360, 390, 430, 768, 1024, and 1440 pixels.
- Verify desktop scene pin/release boundaries, back/forward anchor behavior, keyboard navigation, touch
  content order, and no page-level horizontal overflow.
- With reduced motion enabled, confirm there is no sticky cinematic travel, prompt rotation, pointer
  tracking, or progress bar and that every heading, link, and explanation is immediately visible.
- Record Lighthouse as one signal and inspect the actual LCP element, long tasks, CLS, animation frame
  rate, memory, and hydration cost. Add production RUM for LCP, CLS, and INP.
