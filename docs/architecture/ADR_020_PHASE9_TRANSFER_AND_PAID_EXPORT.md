# ADR 020: Transactional ownership transfer and paid Website export

Status: **Accepted**
Date: **2026-08-10**

## Context

Phase 9 adds the two User-owned Website exit paths: ownership transfer and a paid deployable ZIP
export. Both operations affect durable customer rights, must remain single-owner, and cannot trust
client payment state, callback payloads, query parameters, or local application disks.

No production payment provider or permanent ZIP-export amount has been approved. The product still
requires a Super Admin-controlled price and a verified-payment boundary, but must not fabricate a
checkout or silently substitute an invented price.

## Decision

### Transfers

A sender first validates an active `USER` recipient by normalized email. Validation is read-only;
confirmation is explicit and every command has an idempotency key. Each Website can have one active
transfer workflow at a time.

Draft and offline Websites complete in one transaction: lock the Website and current ownership row,
close the old ownership row, insert the recipient ownership row, change `owner_user_id`, and append
the immutable transfer record. The old owner loses authorization at commit.

For a live Website, the transfer enters `DEACTIVATING` and emits the existing unpublish intent. Only
after Cloudflare/domain routing is confirmed inactive does the worker perform the same ownership
transaction. A failed unpublish marks the transfer failed and preserves the original owner and live
Website. The recipient must complete a normal future publish/domain flow; ownership transfer never
silently reassigns a live route.

### Export pricing, payment, and artifacts

Super Admin maintains versioned, currency-specific export prices in minor units. An inactive or
absent price makes new export purchases unavailable; Zylora does not invent a price. Each
`ExportPurchase` snapshots the selected price ID, version, amount, and currency before a payment is
created. Future price changes cannot alter historic purchases.

A `Payment` has exactly one purpose. Subscription payments keep their existing plan/price relation;
export payments instead reference exactly one export purchase. A verified provider event must match
the payment purpose, amount, currency, payment ID, and globally unique provider event ID before it
can move an export purchase from `PAYMENT_PENDING` to `PAID`. Duplicate events are idempotent and
no client endpoint can mark an export paid.

Paid purchases emit an outbox event. The worker snapshots the immutable requested Website version,
generates an in-memory ZIP, and writes it through the configured private object-storage boundary.
The archive exposes only static Website content plus a minimal manifest; it excludes credentials,
secrets, internal records, payment data, audit data, and other users' data. Generated archives are
checksumed, expiry-bound, and reusable only for their exact paid purchase/version.

An owner receives a short-lived storage URL only after server-side authorization and the `READY`
state check. Test memory storage streams the bytes through the authenticated API because it cannot
issue public URLs. Account/privacy export remains separate and cannot create, download, or satisfy a
paid Website archive.

### Production provider boundary

The deterministic verifier remains test-only. Until an approved production payment provider,
signature contract, and operational configuration exist, checkout creation returns the authoritative
price snapshot with `provider_available=false` and cannot grant an export artifact.

## Consequences

- Every Website continues to have one authoritative current owner; no collaboration path is added.
- A transfer cannot partially change authorization or leave a live route assigned to the former
  owner.
- Exports are never delivered from local disks or untrusted frontend state.
- Deployment must configure private S3-compatible storage before a verified paid export can be
  generated in production.
- Super Admin must configure an approved INR and/or USD export price before customers can start a
  paid export purchase.

## Migration

`20260815_0010_transfer_and_paid_exports.py` is additive except for widening the existing transfer
and payment state constraints. It preserves completed ownership history and subscription payments,
backfills no active export price, and creates no archive for existing Websites. Existing completed
transfers remain terminal `COMPLETED` records.