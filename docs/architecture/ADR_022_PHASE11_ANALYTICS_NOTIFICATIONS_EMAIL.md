# ADR-022: Phase 11 measured analytics, notifications, and transactional email

## Status

Accepted and implemented in Phase 11.

## Decision

Analytics is derived from real, Website-scoped events only. The public page-view endpoint resolves the
active published Website from the request host; it accepts no Website or owner identity from the
browser. Event identifiers are idempotency keys. Session and optional visitor inputs are HMAC-digested
with a Website-specific purpose before persistence, so raw browser identifiers are never stored.

`AnalyticsService` is the only event-ingestion and aggregation boundary. It accepts only known event
types, locks duplicate event keys, verifies the current live owner, and computes timezone-aware daily
rollups in `analytics_daily_rollups`. Portal reads use rollups only. They show a first-publish CTA before
a Website is live and no metrics until meaningful recorded activity exists.

In-app notifications are durable recipient-owned rows with fixed server-authored title, body, and deep
link mappings. A recipient/deduplication advisory lock makes retry safe. User APIs paginate by creation
time and only the recipient may mark an item read.

Transactional email uses encrypted recipient/content fields in PostgreSQL plus the existing durable
outbox. The worker decrypts immediately before calling the SMTP adapter, records bounded retry state,
and uses the stable idempotency key to avoid duplicate sends. Authentication verification and password
recovery use this same queue; the reset URL is encrypted with the message content. Marketing campaigns
remain a distinct later capability and are not implied by the transactional queue.

## Consequences

- Published artifacts emit lightweight same-origin page-view events; Website ZIP exports explicitly omit
  chatbot and analytics platform scripts.
- Analytics remains tenant-isolated across event, rollup, dashboard, and host-resolution paths.
- Provider failures do not falsify delivery: jobs move through `RETRY_WAIT` and eventually `FAILED`.
- Email content and recipient data must never appear in logs, outbox payloads, analytics properties, or
  API responses.