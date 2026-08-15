# ADR-030: Activation, value analytics, attribution, and retention

## Status

Accepted and implemented.

## Context

Phase 11 established AnalyticsService as the canonical Website event and daily-rollup boundary.
Zylora now needs to understand the lifecycle from account creation through a published Website
receiving a legitimate form Lead, without creating a second analytics platform or weakening the
form-only Lead consent boundary.

## Decision

- analytics_events remains the Website activity source used for privacy-safe visitor/session, form,
  chatbot, and Lead rollups.
- product_events stores bounded, non-PII lifecycle facts. Stable idempotency keys make writes retry safe.
- website_value_states is the locked, one-row-per-Website projection for first publication, first
  visitor, and first form Lead. FIRST_LEAD is generated exactly once per Website from
  LeadService.capture; chatbot operations have no path to it.
- First-touch acquisition data is session-scoped in the browser and attached at email signup or
  persisted through the existing OAuth transaction. Only bounded UTM/referrer/landing fields are
  stored. Country is country-level only and production accepts it from the Cloudflare edge header;
  absence is ZZ, never a guessed country.
- Monthly digest and zero-Lead checkpoint records have relational idempotency constraints. Existing
  Celery beat, encrypted transactional email, in-app notifications, and outbox delivery remain the
  only job and messaging systems.
- Super Admin funnel, North Star, and retention projections query persisted state through the
  isolated Super Admin authorization path. User Website outcome metrics remain current-owner scoped.
- The North Star is the count of currently published Websites with a valid FORM Lead in the trailing
  30 days.

## Privacy and security consequences

Analytics properties reject common PII/secret field names and bounded payload size. Lead enquiry
content and chatbot message content are never copied into product events, attribution, or form-open
events. Visitor identifiers remain purpose-HMAC-digested by Website. No fingerprint, GPS request, or
new anonymous backend identity is introduced.

## Operational consequences

One additive migration creates lifecycle/value/attribution/delivery/checkpoint tables, adds form-open
and form-submit rollup counters, and allows the monthly digest transactional email kind. Existing
Lead, chatbot, billing, publishing, notification, and tenant boundaries remain authoritative.
