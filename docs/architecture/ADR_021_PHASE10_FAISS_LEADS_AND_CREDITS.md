# ADR-021: Phase 10 FAISS chatbot, unified Leads, and credit ledger

Status: Superseded in part by ADR-029

## Decision

Phase 10 introduces one Website-scoped FAISS chatbot model and one canonical `LeadService`.
Published Website content is the only knowledge source. A Celery worker extracts structured content from
the immutable published `WebsiteVersion`, chunks it, obtains embeddings, builds a FAISS inner-product
index, stores the index as a private immutable object, validates it, and atomically switches the
Website chatbot's active index.

Every index row and manifest carries Website ID, current owner ID, published version ID, embedding
model/dimension, chunker version, object key, and checksum. Query requests resolve the Website from
the active request hostname; callers cannot provide an owner, index path, or Website ID. Conversation
access also requires the opaque per-conversation capability returned only when that conversation is
created on the same active Website.

The deployed Website renderer includes one platform-authored accessible chatbot widget. Its script is
not Template-authored and inserts all user/assistant text with `textContent`. Paid Website ZIP export
uses the same renderer with the widget explicitly disabled, so no Zylora chatbot endpoint, secret,
conversation data, or runtime dependency is included in an export.

Only explicit Website form submissions use the normalized `Lead` model and `LeadService`. In one
PostgreSQL transaction, the service locks the Website and owner credit account, validates the
idempotency fingerprint, records the Lead, appends exactly one `LEAD_CAPTURE` `-1` ledger entry,
persists an in-app notification and lead analytics event, and enqueues notification intent. Retry with
the same key returns the original Lead; a changed payload is rejected.

`lead_zero_balance_policy` is versioned in `platform_metadata` and Super-Admin configurable. The
initial policy is `ALLOW_DEBT`, which preserves the approved unlimited-lead product rule while still
recording exactly one debit per valid Lead. `REJECT_NEW` is available for an explicit commercial
restriction and is checked before Lead insertion under the same advisory/account lock.

Ownership transfer immediately disables all old chatbot indexes, clears the active pointer, and queues
private artifact deletion. A recipient can only rebind the chatbot after a normal later publish creates
a new index for that recipient's published version.

## Consequences

- `faiss-cpu` and `numpy` are explicit API runtime dependencies; no Pinecone or Chroma adapter exists.
- OpenAI's server-side embeddings endpoint is the production adapter. Tests use a deterministic local
  embedding adapter; it is not selectable in production.
- Public form submission uses Turnstile when enabled; chatbot messages cannot submit Leads. The lightweight chat-message
  interaction relies on the existing Cloudflare WAF/rate limit to avoid interrupting normal visitor
  conversation; it remains Website-host scoped and capability-bound.
- In-app Lead notifications are durable now. Provider delivery is deliberately not fabricated; later
  notification-channel work consumes the committed notification intent.