# Zylora V2 state machines

Status: **Frozen**

All transitions are commands handled by one canonical service, validated against the current state,
authorized server-side, written with optimistic/row locking, audited where sensitive, and accompanied
by outbox events when external work follows. Workers may request transitions but may not write terminal
states directly.

## Account lifecycle

```text
PENDING_VERIFICATION ──verify──> ACTIVE
PENDING_VERIFICATION ──expire/delete──> DELETED
ACTIVE ──security lock──> LOCKED ──verified recovery──> ACTIVE
ACTIVE/LOCKED ──request deletion──> DELETION_PENDING
DELETION_PENDING ──cancel within grace──> ACTIVE
DELETION_PENDING ──complete lifecycle──> DELETED
```

An email/password account cannot enter `ACTIVE` without consumed verification evidence. A verified
Google identity may create `ACTIVE` atomically. Deletion cannot complete while required unpublish,
domain, subscription, retention, or legal/accounting actions are unresolved.

## Verification code

```text
ISSUED ──valid proof──> CONSUMED
ISSUED ──new send──> SUPERSEDED
ISSUED ──time limit──> EXPIRED
ISSUED ──attempt limit──> LOCKED
```

Only `ISSUED` can be verified. Resend creates a new generation and supersedes every earlier live code.
Codes are never restored or logged.

## Website lifecycle

The Website aggregate separates document readiness from deployment attempt details:

```text
DRAFT ──validated ready command──> READY
READY ──edit──> DRAFT
READY ──reserve publish──> PUBLISHING
PUBLISHING ──healthy traffic switch──> PUBLISHED
PUBLISHING ──failure before first live──> FAILED
PUBLISHING ──failure while updating live──> PUBLISHED (old deployment remains active)
PUBLISHED ──begin unpublish──> UNPUBLISHING
UNPUBLISHING ──routing disabled──> UNPUBLISHED
UNPUBLISHING ──provider failure──> PUBLISHED or FAILED, based on verified route state
UNPUBLISHED ──edit──> DRAFT
UNPUBLISHED ──validated ready command──> READY
DRAFT/READY/UNPUBLISHED ──successful ownership transfer──> TRANSFERRED
PUBLISHED ──prepare transfer──> UNPUBLISHING ──routing disabled + transfer──> TRANSFERRED
TRANSFERRED ──recipient accepts project context──> DRAFT
DRAFT/READY/UNPUBLISHED ──begin paid export generation──> EXPORTING
EXPORTING ──artifact ready──> EXPORTED
EXPORTING ──generation failure──> prior state with failed ExportPurchase
FAILED ──recover/edit──> DRAFT
FAILED ──retry verified snapshot──> READY
```

`EXPORTED` records a completed export action; it does not imply a published Website and does not have
to prevent continued editing. The implementation may represent export activity as a parallel
`ExportPurchase` state instead of making `EXPORTED` a permanent blocking Website state; the public
Website lifecycle view derives the latest action without scattering booleans.

Forbidden transitions include direct `DRAFT -> PUBLISHED`, `READY -> PUBLISHED`, publish without a
reserved one-live-site key, transfer that leaves the former live route active, or any transition based
only on frontend state.

## Document revision/validation

```text
VALID ──accepted patch──> VALID (new immutable version)
VALID ──validation request──> VALIDATING ──pass──> VALID
VALIDATING ──fail──> REJECTED
REJECTED ──corrected patch against last valid parent──> VALIDATING
VALID ──restore old version──> VALID (new restore version)
```

The current draft pointer advances only to `VALID`. Failed manual/AI patches are recorded as operation
results, not current WebsiteVersions.

## Template version lifecycle

```text
DRAFT ──submit──> VALIDATING
VALIDATING ──checks pass──> VALIDATED
VALIDATING ──checks fail──> REJECTED
REJECTED ──new immutable correction──> DRAFT
VALIDATED ──admin approve──> APPROVED
APPROVED ──publish──> PUBLISHED
PUBLISHED ──deprecate──> DEPRECATED
DEPRECATED ──restore after current validation──> PUBLISHED
PUBLISHED/DEPRECATED ──security retirement──> RETIRED
```

Only `PUBLISHED` is selectable for new Websites. Existing Websites retain their immutable source
version. `RETIRED` may require security migration/disablement and cannot be restored casually.

## Plan catalog lifecycle

```text
DRAFT ──validate exactly four plans/prices/entitlements──> VALIDATED
VALIDATED ──publish at effective time──> PUBLISHED
PUBLISHED ──replacement becomes effective──> RETIRED
VALIDATED ──commercial rejection──> REJECTED
```

Published catalogs are immutable. Admin price/entitlement changes clone a new draft catalog, preserve
all historical invoices/subscriptions, and atomically switch the effective catalog.

## Publish evaluation

An evaluation is a short-lived read model, not authority for a later publish:

```text
COMPUTING ──complete──> ELIGIBLE | INELIGIBLE | UPGRADE_REQUIRED
ELIGIBLE/UPGRADE_REQUIRED/INELIGIBLE ──input/catalog/version changes or TTL──> STALE
```

The publish command always re-evaluates locked current state. Reasons use stable codes such as
`PAGE_LIMIT_EXCEEDED`, `CUSTOM_DOMAIN_NOT_ALLOWED`, `PAYMENT_REQUIRED`, `ANOTHER_WEBSITE_LIVE`, and
`DOMAIN_NOT_VERIFIED` plus user-safe detail.

## Deployment lifecycle

```text
QUEUED ──worker claim──> VALIDATING
VALIDATING ──pass──> BUILDING
BUILDING ──artifact verified──> PROVISIONING
PROVISIONING ──route/TLS prepared──> HEALTH_CHECKING
HEALTH_CHECKING ──pass──> SWITCHING
SWITCHING ──atomic route success──> ACTIVE
ACTIVE ──replaced──> SUPERSEDED
ACTIVE ──rollback target selected──> ROLLING_BACK ──healthy switch──> ACTIVE
any nonterminal state ──safe failure──> FAILED
QUEUED/VALIDATING ──authorized cancel──> CANCELLED
```

`FAILED` never changes the active deployment pointer. Recovery creates a new attempt; it does not
rewrite history. Provider calls use stable idempotency keys. Ambiguous provider timeout enters a
verification/reconciliation path before retrying a non-idempotent-looking call.

## Domain lifecycle

```text
RESERVED ──custom challenge created──> PENDING_DNS
RESERVED ──Zylora hostname provisioned──> PROVISIONING
PENDING_DNS ──ownership verified──> VERIFIED
PENDING_DNS ──timeout──> VERIFICATION_FAILED
VERIFICATION_FAILED ──retry/new challenge──> PENDING_DNS
VERIFIED ──provider create──> PROVISIONING
PROVISIONING ──TLS and route ready──> ACTIVE
PROVISIONING ──provider failure──> PROVISIONING_FAILED
ACTIVE ──DNS/TLS regression──> DEGRADED
DEGRADED ──verified recovery──> ACTIVE
ACTIVE/DEGRADED ──unpublish/remove──> DEACTIVATING ──provider confirmed──> INACTIVE
```

Hostname uniqueness is reserved before external work. `ACTIVE` requires provider verification and a
healthy deployment. Failure messages expose expected DNS records and observed state, never secrets.

## Ownership transfer lifecycle

```text
REQUESTED ──recipient/self/state validation──> VALIDATED
VALIDATED ──live route exists──> DEACTIVATING
VALIDATED ──draft Website──> COMMITTING
DEACTIVATING ──route confirmed inactive──> COMMITTING
COMMITTING ──locked atomic ownership commit──> COMPLETED
REQUESTED/VALIDATED ──cancel/expire──> CANCELLED
any pre-complete state ──validation/provider/transaction error──> FAILED
```

Only `COMPLETED` changes authorization. If an error occurs before commit, the prior owner remains the
single owner. If notification fails after commit, ownership remains complete and notification retries.

## Subscription lifecycle

```text
PENDING ──checkout challenge──> AUTHENTICATING
AUTHENTICATING ──trusted capture + provider activation──> ACTIVE
AUTHENTICATING ──failure/cancel──> FAILED
ACTIVE ──renewal window──> RENEWAL_PENDING
RENEWAL_PENDING ──trusted renewal──> ACTIVE
RENEWAL_PENDING ──payment failure/grace──> PAST_DUE
PAST_DUE ──successful recovery──> ACTIVE
PAST_DUE ──grace exhausted──> EXPIRED
ACTIVE/RENEWAL_PENDING/PAST_DUE ──cancel at period end──> CANCELLED
CANCELLED ──period end──> EXPIRED
```

Capability-granting states and grace behavior are defined centrally and snapshot provider evidence.
Provider messages cannot move a terminal state backward without an explicit reconciliation rule.

## Payment lifecycle

```text
CREATED ──checkout/order created──> PENDING
PENDING ──customer/provider processing──> PROCESSING
PENDING/PROCESSING ──trusted successful verification──> CAPTURED
PENDING/PROCESSING ──verified failure──> FAILED
PENDING/PROCESSING ──expiry/cancel──> CANCELLED
CAPTURED ──settlement confirmation where relevant──> SETTLED
CAPTURED/SETTLED ──authorized refund request──> REFUND_PENDING
REFUND_PENDING ──provider confirmation──> REFUNDED | PARTIALLY_REFUNDED
ambiguous nonterminal state ──reconciliation──> prior state or verified terminal state
```

Only trusted `CAPTURED`/`SETTLED` according to the payable contract can unlock paid behavior. Amount,
currency, provider purpose metadata, and local payable must all match.

## Export purchase lifecycle

```text
CREATED ──checkout created──> PAYMENT_PENDING
PAYMENT_PENDING ──trusted payment captured──> PAID
PAYMENT_PENDING ──failure/expiry──> FAILED
PAID ──worker claim + payment recheck──> GENERATING
GENERATING ──validated archive stored──> READY
GENERATING ──safe generation failure──> FAILED
READY ──artifact expiry/delete──> EXPIRED
PAID/READY ──authorized refund──> REFUNDED
```

No artifact or download authorization exists in `CREATED`, `PAYMENT_PENDING`, or unverified states.
Generation is idempotent by purchase/version/checksum. Account export has a separate lifecycle and can
never transition an ExportPurchase.

## Lead capture operation

Lead is a transactional operation rather than a long-lived workflow:

```text
RECEIVED -> VALIDATED -> IDEMPOTENCY_CHECKED -> COMMITTED
              └──────── invalid/bot/policy rejection ─────> REJECTED
```

`COMMITTED` means Lead row, exactly one ledger entry, analytics event, and notification outbox intent
committed together. A duplicate key with the same fingerprint returns the prior result; a different
fingerprint is rejected. Notification delivery is asynchronous and cannot roll back a valid Lead.

## Knowledge index lifecycle

```text
REQUESTED ──worker claim──> EXTRACTING
EXTRACTING ──published-content snapshot──> EMBEDDING
EMBEDDING ──complete──> BUILDING
BUILDING ──artifact/checksum complete──> VALIDATING
VALIDATING ──isolation/search smoke pass──> ACTIVE
ACTIVE ──new active index──> SUPERSEDED
any work state ──error──> FAILED
ACTIVE/SUPERSEDED ──Website purge/transfer cleanup──> DELETED
```

The previous `ACTIVE` index remains queryable until a new one validates. Transfer invalidates the old
owner/index access epoch and schedules rebuild for the recipient's published version only after a new
publish.

## Notification/email delivery

```text
QUEUED ──worker claim──> SENDING
SENDING ──provider accepted──> SENT
SENT ──delivery event──> DELIVERED
SENT ──bounce/complaint──> BOUNCED | COMPLAINED
SENDING ──retryable failure──> RETRY_WAIT ──due──> QUEUED
SENDING/RETRY_WAIT ──attempt limit/permanent failure──> FAILED
QUEUED ──marketing suppression──> SUPPRESSED
```

Transactional notifications ignore marketing unsubscribe but still honor provider hard-bounce safety
and security policy. Every retry uses the same message idempotency key.

## Campaign lifecycle

```text
DRAFT ──preview/validation──> READY
READY ──schedule──> SCHEDULED
READY/SCHEDULED ──authorized send──> SENDING
SENDING ──all recipients terminal──> COMPLETED
DRAFT/READY/SCHEDULED ──cancel──> CANCELLED
SENDING ──operator pause──> PAUSED ──resume──> SENDING
any active state ──unrecoverable configuration failure──> FAILED
```

Audience is snapshotted before send. Each recipient delivery is idempotent and suppression is checked
again at send time.

## Blog post lifecycle

```text
DRAFT ──content/SEO validation──> READY
READY ──publish now──> PUBLISHED
READY ──schedule──> SCHEDULED ──due + valid──> PUBLISHED
PUBLISHED ──unpublish──> DRAFT
PUBLISHED ──archive──> ARCHIVED
ARCHIVED ──restore as new revision──> DRAFT
```

Publishing creates an immutable rendered revision and updates sitemap/cache through outbox jobs.

## Background job lifecycle

```text
PENDING ──lease──> RUNNING
RUNNING ──success marker──> SUCCEEDED
RUNNING ──retryable error/lease timeout──> RETRY_WAIT
RETRY_WAIT ──due──> PENDING
RUNNING/RETRY_WAIT ──attempt/age bound──> DEAD_LETTER
PENDING ──authorized cancellation──> CANCELLED
```

Handlers checkpoint only safe resumable state. Job completion is recorded after the external effect
and authoritative transition are verifiably complete.

## Phase 9 implemented transfer and paid-export behavior

The Phase 9 transfer row persists `VALIDATED`, `DEACTIVATING`, `COMPLETED`, `FAILED`, or
`CANCELLED`. Recipient validation is read-only. An offline Website completes within one transaction;
a live Website is first placed in `UNPUBLISHING` with a durable unpublish intent. The worker changes
ownership only after the active route is confirmed inactive. A failed deactivation preserves the
current owner and live Website.

Paid Website export is a parallel `ExportPurchase` workflow. It snapshots an active versioned
Super-Admin price and the exact immutable Website version before checkout. A trusted payment event
moves the purchase to generation and emits a durable outbox intent. Only `READY` with an unexpired
private artifact may be downloaded by the current purchaser/current Website owner. The recipient of a
transfer receives a Draft and follows the ordinary future domain/publish flow.