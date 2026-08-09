# ADR-015: Cloudflare Turnstile and WAF abuse boundary

Status: **Accepted**
Date: **2026-08-09**

## Context

Phase 2 requires layered abuse controls for public authentication and isolated Super Admin access.
Application rate budgets remain authoritative, but they cannot filter network-layer scanner traffic
or distinguish automated browser traffic alone. A hosted challenge requires an explicit privacy and
secret-management decision because a challenge token and visitor IP leave Zylora.

The product owner explicitly approved Cloudflare Turnstile and Cloudflare WAF for this boundary.

## Decision

- Use a managed Turnstile widget with `no_clearance`, exact User/Admin hostnames, explicit rendering,
  and `interaction-only` appearance.
- Require server-side Siteverify on signup, email verification/resend, User login, Google OAuth start,
  password recovery request/confirm, and Super Admin login. Normal authenticated portal commands are
  not challenged.
- Send Cloudflare only the server-held secret, short-lived response token, visitor IP, and a random
  verification idempotency key. Validate `success`, exact action, and exact hostname. Never persist or
  log the response token or provider secret.
- Treat missing, invalid, expired/replayed, wrong-host, and wrong-action responses as rejection.
  Provider/configuration failure fails closed with a generic 503 response.
- Preserve Google OAuth and email/password plus email verification. Do not add a Super Admin
  six-digit-code step; the only account types remain `USER` and `SUPER_ADMIN`.
- Manage Cloudflare Managed Rules, OWASP Core Rules, method restrictions, and route-specific rate
  limits in `infra/cloudflare`. Edge controls complement rather than replace application
  authorization, CSRF/origin checks, and PostgreSQL abuse budgets.

## Consequences

Production cannot start with Turnstile disabled, missing keys, Cloudflare test keys, or hostnames that
differ from configured User/Admin origins. The public site key is runtime data; the secret remains
server-only. Terraform state must be encrypted and access-controlled because the widget provider may
store sensitive material there. A Cloudflare outage blocks protected public auth commands by design;
existing authenticated product use is unaffected.
