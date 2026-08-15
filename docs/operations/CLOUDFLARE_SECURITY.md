# Cloudflare Turnstile and WAF operations

## Provisioning

`infra/cloudflare` is the production source of truth. It provisions one managed Turnstile widget for
the User/Admin hostnames plus approved public Website hostnames, Cloudflare Managed and OWASP WAF rules, invalid
method/scanner blocks, and rate limits for authentication, verification, OAuth callback, public APIs,
contact/Lead forms, and chatbot endpoints.

Phase 6 also rate-limits authenticated POST editor/ai-edits requests to ten plans per visitor IP per
minute. It does not add Turnstile to normal authenticated editing interactions.

Use the pinned Terraform CLI/provider versions. Provide `CLOUDFLARE_API_TOKEN`,
`TF_VAR_account_id`, `TF_VAR_zone_id`, and a two-item `TF_VAR_turnstile_domains` through the deployment
secret manager. Grant only Account Turnstile Sites write/read and Zone WAF write/read permissions.
Use encrypted remote Terraform state with locking and audit logs.

The production change procedure is:

1. Proxy the User, Admin, and API records through Cloudflare and confirm origin certificates/TLS.
2. Run `terraform init`, `terraform fmt -check`, `terraform validate`, and review `terraform plan`.
3. Apply through the audited deployment workflow. Check plan limits before apply; managed/OWASP and
   advanced rate-limit availability varies by Cloudflare subscription.
4. Put the output site key in server runtime `TURNSTILE_SITE_KEY`. Retrieve the widget secret directly
   from Cloudflare into `TURNSTILE_SECRET_KEY`; never place it in Terraform output or a frontend
   environment variable.
5. Set `TURNSTILE_ENABLED=true` and `TURNSTILE_ALLOWED_HOSTNAMES` to the exact User/Admin hostnames. For public lead/chatbot commands, the API additionally verifies the Siteverify hostname against the active Website host resolved server-side; configure that host in the Turnstile dashboard before enabling its public widget.
6. Smoke-test every protected route, inspect WAF events, then tune false positives through reviewed
   ruleset changes. Do not bypass Turnstile or application authorization to resolve a false positive.

Restrict the origin firewall/load balancer to Cloudflare egress where the deployment supports it.
Configure `TRUSTED_PROXY_IPS` only for the immediate trusted proxy so visitor IP handling cannot be
spoofed by public `Forwarded` or `X-Forwarded-For` headers.

## Runtime and privacy boundary

The browser loads only Cloudflare's public challenge script and site key. The API sends Siteverify the
response token, visitor IP, random request idempotency key, and server-only secret. It sends no email,
password, account ID, role, form payload, cookie, user agent, or application metadata. Tokens are
single-use, expire in five minutes at Cloudflare, remain only in browser/server request memory, and
are never logged or stored.

Siteverify success is accepted only when its hostname and action exactly match the server's expected
values. Missing, invalid, expired, duplicate/replayed, wrong-host/action, timeout, malformed response,
or provider outage fails securely. Audit records contain only the expected action, normalized reason,
correlation ID, and a purpose-digested IP value.

## Local and automated testing

`.env.example` uses Cloudflare's documented public always-pass test keys. Production configuration
rejects all documented test keys. Unit tests mock Siteverify deterministically and cover valid,
invalid, missing, expired/replayed, host/action mismatch, duplicate behavior, and provider failures.
The Terraform validation gate requires no Cloudflare credentials and never applies resources.

## Monitoring and response

Alert on challenge rejection/outage rates, WAF blocks, rate-limit activations, and unexpected changes
in action/hostname failures without logging tokens. During a Cloudflare outage, keep protected auth
commands closed, preserve existing authenticated sessions, publish status communication, and follow
the DNS/Cloudflare incident procedure. Rotate a suspected widget secret in Cloudflare and the server
secret manager, invalidate the old secret, and verify repository/log history remains clean.

## Phase 11 public analytics route

`/api/v1/public/analytics/page-views` belongs to the public API rate-limit rule. It intentionally has no
Turnstile challenge: it is emitted from normal published-page views. The API instead requires a strict
opaque-ID schema, active host-to-Website resolution, server-side HMAC attribution, event idempotency,
and the Cloudflare WAF/rate limit. Do not broaden the rule to trust a client Website ID or record raw IP,
email, Lead, or chatbot content.
## Phase 14 public contact route

`POST /api/v1/public/contact` is covered by the public contact/form WAF and rate-limit rule. Its
Turnstile action is exactly `contact`; the API independently validates the action and hostname,
queues the message only after verification, and uses the configured internal recipient. A
Cloudflare outage, invalid token, replay, or unavailable recipient fails closed and sends no email.