# ADR-023: Phase 13 Super Admin campaigns and Blog

## Status

Accepted and implemented in Phase 13.

## Decision

Marketing campaigns and public Blog publishing are isolated Super Admin capabilities. There is no
Marketing Admin role and no client-side audience export.

`CampaignService` is the only campaign aggregate writer. It validates the state transition, resolves
the audience from server-side user, subscription, and Website state at send time, snapshots one
recipient row per user, rechecks marketing suppression at delivery, and emits one durable delivery
outbox event per eligible recipient. Recipient email addresses and unsubscribe tokens are encrypted
at rest; only token digests are compared. Delivery attempts use stable recipient idempotency keys and
bounded retry. The worker records provider acceptance and failure facts only; it does not invent
opens, clicks, or deliveries that the configured provider did not report.

The public unsubscribe endpoint accepts only the opaque token and creates a `MARKETING` suppression.
It never blocks transactional, security, account, or other required email. Worker-generated
unsubscribe links use the configured User Web origin, rather than an untrusted request origin.

`BlogService` is the only Blog aggregate writer. Blog posts move through Draft, Ready, Scheduled, and
Published states. Publication creates an immutable rendered revision and scheduled publication is
performed by a bounded periodic worker. Public reads include published posts only. The canonical path
is `/blog/{slug}`; the Web application generates metadata, Open Graph data, Article JSON-LD,
breadcrumbs, related internal links, and the sitemap dynamically from published server data.

## Consequences

- Campaign recipient data and raw email addresses never appear in browser API responses, audit
  metadata, logs, or outbox payloads.
- Campaign reporting exposes only durable counts: provider accepted, failed, suppressed, and
  unsubscribed. Additional provider webhooks may add future measured event types without changing
  this authority boundary.
- Blog HTML is rendered server-side from escaped content. Raw authored HTML is never trusted.
- Campaigns and Blog content are independently auditable using the existing Super Admin audit trail.
- The implementation introduces no collaboration role, paid entitlement shortcut, or user-level
  content administration path.