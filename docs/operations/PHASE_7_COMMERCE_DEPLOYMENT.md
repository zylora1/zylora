# Phase 7 commerce deployment controls

Phase 7 introduces the permanent monthly catalog, subscription/payment snapshots, ownership transfer,
publish eligibility, one-live-Website reservation, AI allowance synchronization, and WhatsApp
notification quotas. It does not approve or configure a production payment provider.

## Required runtime configuration

Use `CLOUDFLARE_COUNTRY_HEADER_TRUSTED=false` unless the API origin accepts traffic only from
Cloudflare. Once origin restriction is demonstrably enforced, set it to `true` to persist a valid
`CF-IPCountry` value for a User with no verified billing country. Requests never accept a browser
region parameter. Unknown countries use the International catalog.

Keep the Cloudflare ruleset in `infra/cloudflare` applied through the audited infrastructure workflow.
It adds rate limits for the public plan catalog, checkout snapshot creation, publication/unpublication,
and ownership transfer. These signed-in actions retain API origin, CSRF, authorization, and
idempotency validation. They intentionally do not add Turnstile to ordinary authenticated product
workflows.

## Payment boundary

The API may create a server-side payment snapshot but returns `provider_available=false` until a
production provider is separately approved and configured. The bundled deterministic verifier is
test-only and refuses all non-test environments. Do not route a production webhook to it or grant a
paid subscription from a success redirect.

Before enabling a provider, implement and verify its adapter with:

- server-generated amount/currency/plan snapshots;
- authenticated and replay-safe webhook verification;
- provider event idempotency and reconciliation;
- country/billing-country handling that cannot be client controlled;
- a payment secret held only in deployment secret storage.

## Operational checks

1. Apply the Phase 7 migration through the normal release workflow.
2. Confirm the current regional catalog returns exactly Free, Basic, Growth, and Business, with Growth
   as the single Most Popular plan.
3. Confirm a 30-page Draft remains editable, then returns Business-only eligibility at publish time.
4. Confirm the one-live Website unique index blocks a concurrent second publish reservation.
5. Confirm a WhatsApp quota limit suppresses notification delivery but preserves the Lead record.
6. Review Cloudflare WAF/rate-limit events after deployment. Terraform/OpenTofu validation still
   requires the pinned CLI and Cloudflare credentials in the release environment.
