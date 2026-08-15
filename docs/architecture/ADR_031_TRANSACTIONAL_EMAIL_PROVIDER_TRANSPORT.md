# ADR-031: Provider-selected transactional email transport

## Status

Accepted for the staging deployment.

## Context

Transactional email is already isolated behind `TransactionalEmailProvider` and the durable
PostgreSQL outbox. The initial implementation constructs the SMTP adapter directly in Celery.
Railway disables outbound SMTP on Free, Trial, and Hobby plans and requires a transactional email
provider's HTTPS API on those plans.

Changing the transport must not change queue ownership, encrypted message storage, retry timing,
message rendering, routes, or delivery-state semantics.

## Decision

Runtime configuration selects `smtp` or `resend` through `EMAIL_PROVIDER`.

- `smtp` retains the authenticated SMTP adapter and remains the local-development default.
- `resend` sends the already-rendered plain-text message through Resend's official HTTPS email API
  using `RESEND_API_KEY` and the existing `SMTP_FROM_EMAIL` sender identity.
- Celery obtains the selected implementation from one provider factory for transactional and
  campaign email.
- Resend requests use a deterministic, non-secret idempotency key derived from the complete rendered
  message so an ambiguous HTTP retry cannot duplicate the same message.
- Provider credentials, recipients, message bodies, and provider response bodies are never logged.

The durable outbox remains the only delivery state machine. A provider exception continues to move
the job through the existing bounded retry sequence and eventually to `FAILED`; no adapter may
return fake success.

## Consequences

- Railway plans without SMTP egress can deliver email over HTTPS without weakening retry behavior.
- Production validation requires credentials for the selected provider instead of requiring SMTP
  unconditionally.
- Verification, password reset, ownership transfer, Lead notification, and campaign semantics remain
  unchanged because their existing services continue to submit the same rendered messages.
