# ADR-024: Phase 14 public experience and contact boundary

## Status

Accepted and implemented in Phase 14.

## Decision

The public Zylora experience is one shared marketing shell for the landing page, Templates, pricing,
Journal, contact, and legal pages. It describes only implemented product behavior: approved
Template-first Website creation, structured manual and AI editing, draft ownership, publishing,
transfer/export where eligible, and the User portal. It does not make invented customer, social
proof, uptime, SEO-ranking, or delivery claims.

Public Template catalogue and detail pages derive their content from the published-and-approved
Template API only. The gallery remains cursor-paginated and the XML sitemap iterates the same bounded
catalogue contract. Responsive previews remain `noindex`; they are an inspection surface rather than
a competing landing page. Published Blog posts remain the only dynamic Blog entries available to
metadata, Article structured data, and the sitemap.

`POST /api/v1/public/contact` is a deliberately narrow anonymous command. It validates its compact
payload, requires the existing server-side Cloudflare Turnstile verification with the `contact`
action, receives the visitor IP only through the existing trusted-proxy boundary, and queues a
`CONTACT_SUBMISSION` transactional delivery with a stable privacy-safe idempotency key. It has no
client-supplied recipient, ownership, role, tenant, or capability parameter. The transaction email
record is the durable internal submission/delivery record; the browser sees only an accepted status
and opaque ID. Production configuration rejects startup without `CONTACT_RECIPIENT_EMAIL`.

## Consequences

- Shared navigation and footer create a single keyboard-accessible public information architecture.
- Canonicals, Open Graph metadata, Organization/WebSite/FAQ/Article/Breadcrumb structured data,
  robots, and sitemap entries describe actual public content only.
- Public contact delivery fails closed when Turnstile is unavailable or the destination is missing;
  the existing Cloudflare WAF/rate-limit policy remains the edge abuse control.
- Contact message contents and visitor identity never appear in public API responses, logs, or
  frontend runtime configuration. Cloudflare receives only the documented Siteverify minimum.
- No public route can grant paid capability, create a blank Website, bypass a Template approval
  state, or introduce a third account type/collaboration path.