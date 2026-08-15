# Phase 10 operations: FAISS chatbot, Leads, and credits

## Required runtime configuration

Set these server-only values before enabling production chatbot indexing:

- `AI_PROVIDER=openai` and `OPENAI_API_KEY` with an embeddings-capable account;
- `OPENAI_BASE_URL=https://api.openai.com/v1` unless an approved provider adapter is introduced;
- `CHATBOT_EMBEDDING_MODEL=text-embedding-3-small` (or an approved model);
- `CHATBOT_EMBEDDING_DIMENSION` matching that model exactly;
- private S3-compatible object storage and a running worker.

`faiss-cpu` and NumPy are application dependencies. FAISS artifacts are private objects under a
server-generated `faiss/<website>/<owner>/<index>/<checksum>.index` key. They are never served from a
public bucket, written to durable application disk, or selected by a browser path/owner parameter.

## Lifecycle

A successful publish enqueues `chatbot.index_requested`. The worker processes the durable event,
extracts only the immutable published version, builds and smoke-tests a new FAISS artifact, then makes
it active atomically. A prior active index stays available until the replacement validates. Build
failure leaves the prior active index intact and marks the new request failed.

Ownership transfer disables indexes before the owner changes and queues `chatbot.cleanup_requested`.
The cleanup worker removes the old private artifact. Recipient access starts only after a later normal
publish has created a fresh recipient-scoped index.

## Lead credits and notifications

`lead_zero_balance_policy` is stored in PostgreSQL and defaults to `ALLOW_DEBT`. Super Admin can use:

- `GET/POST /api/v1/admin/lead-credit-policy`
- `POST /api/v1/admin/users/{user_id}/lead-credits` with CSRF protection and an `Idempotency-Key`.

Every valid Lead creates exactly one append-only `LEAD_CAPTURE` ledger entry of `-1`; the database
trigger forbids ledger updates/deletes. Duplicate submission retries return the existing Lead without
another debit. Lead contact information remains stored even when WhatsApp notification quota is
exhausted. In-app notification and analytics-event records are committed with the Lead; external
channel delivery is not claimed unless a configured provider accepts it.

## Public security controls

Public form Leads are server-side Turnstile-protected when enabled. Chatbot conversations cannot
create Leads and their messages are never submitted to the Lead service.
Siteverify's hostname must equal the active Website hostname resolved from the incoming request, not a
client-supplied Website ID. Configure each enabled public Website hostname in the Cloudflare Turnstile
dashboard. Cloudflare Terraform rate-limits `/api/v1/public/leads` and
`/api/v1/public/chatbot` at 20 requests/IP/minute.

The deployed widget begins a host-scoped conversation and keeps its opaque capability in page memory.
It never sends an owner ID, object key, FAISS ID/path, provider secret, or draft content. All API
routes return fail-closed `404`/`503` states when Website, active route, conversation capability, or
active index checks fail.

## Verification

Run:

```powershell
npm run migrate
npm run migrate:check
uv run pytest apps/api/tests/integration/test_chatbot_leads_phase10.py --run-integration
uv run pytest apps/worker/tests/test_worker_foundation.py
npm run test:integration
npm run typecheck
npm run lint
npm run test
npm run build
npm run test:e2e
npm run security
```