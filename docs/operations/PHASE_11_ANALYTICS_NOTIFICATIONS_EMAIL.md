# Phase 11 operations: analytics, notifications, and transactional email

## Runtime behavior

The API records real page views at `POST /api/v1/public/analytics/page-views`. The active Website comes
from the request hostname and must be published with a live owner. The browser supplies opaque event and
session identifiers only; the API stores Website-purpose HMAC digests, not the raw values.

Celery runs these durable jobs:

- `zylora.notifications.dispatch_transactional_email` every 10 seconds, followed by one idempotent
  `zylora.notifications.process_transactional_email` job per claimed outbox event.
- `zylora.analytics.refresh` every 60 seconds to recompute recent timezone-aware daily rollups.

The User portal reads `GET /api/v1/analytics?period_days=7|30|90` and `GET /api/v1/notifications`. It
renders no synthetic charts. A User can mark only their own notification read through the CSRF-protected
`POST /api/v1/notifications/{notification_id}/read` command.

## Delivery and recovery

`transactional_emails` keeps recipient and rendered content encrypted with the application authentication
secret. Its outbox payload has only the job ID. SMTP provider failures retry with 1, 2, and 4 minute
delays, then become `FAILED`; inspect the safe error code and requeue only through an audited operation.
Do not copy ciphertext, recipient addresses, password-reset links, or provider credentials into logs.

The local Mailpit setup remains useful for delivery smoke tests. Production requires an authenticated
SMTP provider and uses secrets only from the deployment secret manager.

## Analytics privacy and retention

The implementation records page path plus optional purpose-digested session/visitor values. Do not add
email addresses, IP addresses, free-form Lead content, prompt text, or raw chatbot messages to analytics
properties. Retention for raw events must be configured before production scale; daily rollups are the
portal query source and may be retained longer subject to the product privacy policy.

## Cloudflare

The public analytics endpoint is protected by the public API WAF/rate-limit path group. It is deliberately
not Turnstile-gated because every genuine page visit would otherwise be challenged; abuse protection is
edge rate limiting plus strict schema, host resolution, idempotency, and server-side attribution.