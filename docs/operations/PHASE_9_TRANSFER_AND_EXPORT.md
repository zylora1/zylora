# Phase 9: ownership transfer and paid Website ZIP export

## Operating model

Phase 9 provides two User-owned Website exit paths without adding collaborators, teams, or alternate
roles:

- Ownership transfer validates an existing active `USER`, requires `OWNER_TRANSFER_V1` confirmation,
  and changes Website ownership only in a locked transaction.
- A Draft/offline Website transfers immediately. A published Website enters `UNPUBLISHING`; the
  transfer completes only after the provider confirms routing inactive. The former owner loses Website
  authorization in that same commit. The recipient receives a Draft and chooses a normal later domain
  and publish flow.
- Website ZIP export is paid independently of publishing plans. The user first gets a server-selected,
  versioned price snapshot for their persisted billing region, then a local `EXPORT` payment record.
  Only a trusted payment verifier can queue archive generation.

## Super Admin price setup

No export price is seeded because no permanent amount was approved. Before enabling purchases, the
isolated Super Admin must authenticate and create a positive minor-unit price at:

```text
POST /api/v1/admin/export-prices
{
  "currency": "INR" | "USD",
  "amount_minor": <positive integer>,
  "active": true
}
```

Setting a new active price deactivates the prior active price only for that currency. Existing
`ExportPurchase` rows retain their price ID, version, amount, and currency. User requests never
accept a region, currency, or amount.

## Payment-provider boundary

The only verifier currently implemented is deterministic and refuses to initialize outside test.
Consequently, checkout creation deliberately returns `provider_available=false` until an approved
production payment provider, signed webhook contract, secret-management setup, reconciliation policy,
and observability runbook are approved. No UI or API request can mark an export paid, generate a ZIP,
or download an artifact while payment is pending.

## Object storage and delivery

Export archives are generated in memory by the worker and written through the same private
S3-compatible object-storage boundary as immutable publication artifacts. Production must configure
`STORAGE_PROVIDER=s3` and all required S3 values; the test-only memory adapter cannot issue a public
URL. The authenticated owner receives a five-minute presigned URL only after `READY` and expiry
checks. Production buckets must remain private, encrypted, and prevent public object listing/read.

The archive contains static rendered pages, a minimal manifest, and a README. It intentionally omits
raw Website documents, payment records, audit data, database data, credentials, tokens, secrets, and
other users' content. Account/privacy export is a separate future feature and cannot satisfy or
access a paid Website export.

## Worker operations

The worker adds a ten-second `zylora.exports.dispatch_outbox` schedule. It leases only
`export.generate_requested` outbox events, invokes the idempotent export generator, and releases the
lease in all terminal paths. Generation failure records a safe `FAILED` purchase state; it never
returns a partial archive or a success response.

## Release checks

Run the Phase 9 integration suite after applying the migration:

```powershell
npm run migrate
uv run pytest apps/api/tests/integration/test_transfer_exports_phase9.py --run-integration
npm run migrate:check
npm run contracts:check
```

Migration `20260815_0010_transfer_and_paid_exports.py` is additive except for widening existing
transfer/payment constraints. It preserves completed transfers and subscription payments, creates no
export artifacts, and leaves export pricing inactive until a Super Admin configures it.