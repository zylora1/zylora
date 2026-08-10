# Phase 13: Campaigns and Blog operations

## Release prerequisites

1. Apply migration `20260818_0013_campaigns_blog` through `npm run migrate`.
2. Configure a production SMTP provider and a User Web origin in `WEB_ORIGINS`. Campaign delivery
   uses the first explicit approved User Web origin for unsubscribe links.
3. Keep the worker and Celery Beat active. Required periodic tasks are:
   - `zylora.campaigns.dispatch_deliveries` (10 seconds)
   - `zylora.campaigns.start_scheduled` (30 seconds)
   - `zylora.blog.publish_scheduled` (30 seconds)
4. Verify `/blog`, `/blog/{slug}`, `/sitemap.xml`, and `/unsubscribe?token=...` from the public User
   Web origin after deployment.

## Super Admin operating model

Campaigns are created as `DRAFT`, then explicitly prepared (`READY`) before Send or Schedule. Audience
selection is a server-side segment only: all active users, free, paid, plan, recent, users with a draft,
or users without a published Website. The browser receives only aggregate counts after a send begins.
No normal User or public caller can create, inspect, edit, schedule, or send a campaign.

Use manual administrative email for a single User where needed. It uses the existing transactional
email queue and remains distinct from campaign suppression.

Campaign delivery is at-least-once and recipient-idempotent. The worker records provider acceptance
and failures. A provider failure retries with bounded exponential backoff; terminal failures remain
visible in aggregate metrics. SMTP acceptance is not an open/click/delivery claim. Do not report these
metrics until a provider webhook has recorded them.

Unsubscribe is scoped to marketing. It creates an `email_suppressions` record and rechecks that scope
immediately before every queued delivery. Account verification, password recovery, and other required
transactional email remain deliverable.

## Blog operating model

A Blog post is Draft until a Super Admin prepares it. Only Ready posts can be published or scheduled.
The worker publishes due scheduled posts using the same `BlogService` transition as the manual Publish
command. Publishing snapshots an immutable version and makes the post visible at `/blog/{slug}`.

Authors should use title, excerpt, taxonomy, SEO title/meta, Open Graph fields, and logical paragraphs.
A paragraph beginning with `# ` or `## ` renders as a safe `h2`; raw HTML is escaped. Check the rendered
post, page metadata, canonical path, Article JSON-LD, breadcrumbs, related links, and sitemap before
announcing a major article.

## Incident response

- SMTP/provider incident: leave campaign state and recipient events intact; fix provider configuration
  and let bounded retries complete. Do not manually mark unverified delivery as successful.
- Incorrect campaign: cancel before delivery. Already provider-accepted messages cannot be recalled;
  use a separately audited follow-up if necessary.
- Incorrect published Blog post: unpublish it. The current public path stops resolving while immutable
  historic versions remain available for audit/recovery work.
- Worker backlog: investigate outbox leases, `available_at`, `attempts`, and provider safe error codes;
  do not replay raw delivery manually outside the worker/service boundary.