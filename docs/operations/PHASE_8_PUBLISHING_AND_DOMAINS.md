# Phase 8 publishing and domains

Phase 8 deploys an immutable Website-version artifact through the database outbox. A deployment is
not live until its Cloudflare route, TLS state, and deployment-specific health endpoint pass. The
previous active deployment remains the live pointer if a later deployment fails.

## Required production configuration

Set these server-only environment variables in the deployment secret store; do not add them to a
frontend environment, browser response, log, or repository:

- `DOMAIN_PROVIDER=cloudflare`
- `CLOUDFLARE_API_TOKEN` with least-privilege Zone DNS and Cloudflare for SaaS custom-hostname access
- `CLOUDFLARE_ZONE_ID`
- `CLOUDFLARE_PUBLISHED_ORIGIN`, the HTTPS origin used by Cloudflare to reach the Zylora publisher
- `PUBLISHED_SITE_BASE_DOMAIN`, a DNS zone delegated to Zylora for generated subdomains
- private S3-compatible artifact storage settings already required by the API

Production settings reject a disabled domain provider, missing Cloudflare values, and local
publication hosts. `memory` adapters are accepted only in automated test settings. A disabled or
unreachable provider fails a deployment safely; it never marks the Website live.

## Cloudflare dashboard setup still required

1. Delegate the selected Zylora subdomain zone (for example, `sites.example.com`) to Cloudflare and
   configure the publisher origin only behind Cloudflare.
2. Enable Cloudflare for SaaS custom hostnames for the zone and configure the publisher origin,
   including the appropriate origin SNI/certificate policy.
3. Create a scoped API token for the production zone. Store it only in the runtime secret manager.
4. Restrict direct origin access to Cloudflare egress and retain the existing WAF/rate-limit rules.
5. Run a Celery worker and Celery Beat. Beat invokes `zylora.publishing.dispatch_outbox` every ten
   seconds; workers process each leased, idempotent event.

## Customer domain flow

Only a plan with the custom-domain entitlement may request a custom hostname. The API reserves the
normalized hostname, returns Cloudflare's ownership verification record, and then verifies both
ownership and TLS server-side. Publishing a custom hostname before it is `VERIFIED` is rejected.
The customer never provides a Cloudflare token.

## Recovery and rollback

Deployment records and their transition events are retained. A failed candidate leaves the prior
`ACTIVE` deployment pointer intact. A rollback queues a fresh deployment of a prior immutable
Website version and goes through the same validation, artifact, Cloudflare, and health checks. An
unpublish request disables the provider route before releasing the User's one-live-Website slot.

No Cloudflare credentials or production dashboard changes are included in this repository change.

## Phase 8 completion record

**Status: PASS — 2026-08-10**

The Phase 8 release gate was verified with the repository commands below:

- Backend unit suite: passed.
- Backend integration suite: `26 passed, 1 skipped`.
- Authoritative backend coverage: `194 passed, 1 skipped`, **91.13%** (threshold: 90%).
- Frontend suite: `53 passed` with global frontend coverage thresholds satisfied.
- Frontend/backend typecheck, lint, format, production build, security, migrations, template contracts,
  and production-web E2E: passed (`25 passed, 3 skipped` E2E).
- The shared OpenAPI and generated TypeScript API contract include the domain, publication-status,
  deployment, and rollback commands.

Phase 8 deliberately does not contain Cloudflare production credentials or dashboard mutations.
The dashboard steps above remain the required production handoff.