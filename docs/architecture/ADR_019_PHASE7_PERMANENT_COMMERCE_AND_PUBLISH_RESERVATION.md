# ADR 019: Permanent commerce catalog and publish reservation

Status: **Accepted**
Date: **2026-08-09**

## Context

Phase 7 fixes Zylora's active monthly pricing, plan entitlements, publish eligibility, single-owner
authorization, one-live-Website rule, AI allowances, and WhatsApp-notification quotas. Users must be
able to build any-size Draft before subscribing. A payment provider and the Phase 8 deployment
pipeline are not yet approved or implemented.

## Decision

### Immutable regional catalogs

PostgreSQL stores two immutable, published monthly catalog snapshots. India is INR 0/39900/99900/
199900 minor units; International is USD 0/900/1900/3900 minor units for Free, Basic, Growth, and
Business respectively. Growth alone is `most_popular`. There is no annual catalog, annual toggle,
or derived foreign-exchange price.

The server chooses India only from a persisted billing country of `IN`, or from `CF-IPCountry` when
the origin is demonstrably restricted to Cloudflare and `CLOUDFLARE_COUNTRY_HEADER_TRUSTED=true`.
Client region parameters are ignored. An unknown country fails safely to International pricing.

### Entitlements and quota behavior

Published page maxima are 1, 5, 20, and unlimited. Paid tiers include custom domains and remove
Zylora branding. Monthly AI allowances are 15, 100, 500, and 1,500. Monthly WhatsApp notification
allowances are 0, 150, 750, and 2,000. Lead capture is unlimited on every tier.

AI uses the existing row-locked account and ledger. The effective subscription period controls its
reset; Free uses a calendar-month period. WhatsApp reservations use a separate row-locked account and
append-only ledger. Exhaustion suppresses only the notification: the valid Lead is still committed,
visible, and eligible for analytics.

### Publish is a reservation, not fabricated deployment success

The Phase 7 publish command locks the Website and the User live-site key, recomputes requirements,
checks the effective subscription, and reserves `live_owner_user_id`. A unique partial database index
allows at most one PUBLISHING, PUBLISHED, or UNPUBLISHING Website for a User. Success enters
`PUBLISHING` and emits an outbox intent. It does not enter `PUBLISHED` or claim a live route.

Phase 8 owns build, domain, TLS, health checks, traffic switching, and terminal publication. A pending
Phase 7 reservation may be cancelled back to Draft. A genuinely published Website must complete the
unpublish workflow before another Website can reserve the live slot.

### Subscription reuse and downgrade safety

Eligibility returns all four plans with stable reasons. If the effective plan satisfies the Website,
the publish command reuses it without checkout. Otherwise, only eligible upgrades are selectable.
Draft editing, preview, save, and ownership transfer do not call page-limit eligibility.

Plan changes never delete Website pages or revisions. A lower plan restricts a later publish or
republish only. Manual editing and an already-live Website are not disabled when AI credits run out.

### Payment fail-closed boundary

Checkout creation records the selected current catalog, plan, price, exact amount minor, currency,
purpose, and idempotency key. It cannot grant entitlement. The only verifier implemented in Phase 7
is deterministic and refuses to initialize outside the test environment. Production paid checkout
therefore reports unavailable until an approved provider adapter, signature contract, and operational
decision exist. A verified test event must match amount, currency, period, payment, and unique event
ID before one subscription and invoice are committed.

### Ownership and collaboration

Each Website has one `owner_user_id` and exactly one current ownership-history row. Atomic transfer
closes the prior row, inserts the recipient row, changes authorization, and records immutable transfer
evidence. A live or publishing Website must be unpublished first. No collaborator, invite, team,
shared-permission, or seat schema or authorization path exists, so no destructive legacy migration is
needed.

## Consequences

- Catalog and historical commercial rows are immutable; future changes require a new catalog.
- Unknown geography gets International pricing rather than an untrusted India discount.
- Cloudflare country trust is a deployment assertion and stays disabled by default.
- Phase 7 can prove eligibility and reserve one live slot without pretending Phase 8 completed.
- Production checkout remains intentionally unavailable, which is safer than a fake success path.

## Migration

`20260813_0008_commerce_publish_entitlements.py` is additive. It adds billing country, regional
catalogs, subscription/payment/invoice records, notification quota records, Lead storage, publish
reservation columns, ownership history, and transfer history. Existing Websites receive one
deterministic current ownership row. Existing published rows receive `live_owner_user_id` before the
one-live constraint is installed. No Website page or revision data is removed.
