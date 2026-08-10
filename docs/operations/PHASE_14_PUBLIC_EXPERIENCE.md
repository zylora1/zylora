# Phase 14: Public experience operations

## Release prerequisites

1. Apply migration `20260819_0014_public_contact` through `npm run migrate`. The migration extends
   the existing transactional-email kind constraint without deleting historical data. It refuses
   downgrade while contact deliveries remain, preserving auditability.
2. Set `CONTACT_RECIPIENT_EMAIL` to a monitored internal mailbox in the secret manager. Production
   startup now rejects an empty value. It is a destination, not a browser-exposed setting.
3. Apply the reviewed `infra/cloudflare` plan. Confirm `/api/v1/public/contact` receives the public
   API/contact rate limit and the `contact` Turnstile action is valid for the User Web hostname.
4. Keep `TURNSTILE_ENABLED=true`, server-only `TURNSTILE_SECRET_KEY`, exact allowed hostnames, SMTP
   delivery, and the worker/outbox dispatcher configured. Never place a secret in a `NEXT_PUBLIC_`
   variable, Terraform output, client log, or support ticket.
5. Verify `/`, `/templates`, an approved `/templates/{slug}`, `/pricing`, `/blog`, `/contact`, the
   legal pages, `/robots.txt`, and `/sitemap.xml` on desktop and a narrow mobile viewport.

## Public contact procedure

The form requires name, email, message, and Turnstile whenever challenge enforcement is active.
The API repeats validation and never trusts client challenge completion. A successful request returns
`202` only after the durable transactional delivery has been queued. An expired, replayed, invalid,
wrong-action, or provider-unavailable challenge returns a safe error and creates no delivery.

Review contact submissions in the configured internal delivery mailbox and the transactional-email
operations view. Treat repeated messages as idempotent retries when they share the same normalized
email and message digest. Do not copy contact content into public dashboards or logs.

## SEO and accessibility release check

- Confirm one logical `h1` per marketing page, visible keyboard focus, labeled form inputs, and
  error/status announcements on contact.
- Inspect canonical URL, title, description, Open Graph tags, robots behavior, and structured data
  for a landing page, approved Template, and published Blog article.
- Confirm private `/app`, `/admin`, and `/api` paths are noindexed/disallowed and never appear in
  the sitemap.
- Do not add fabricated testimonials, logo walls, social metrics, performance claims, legal
  guarantees, or schema facts that Zylora cannot substantiate.