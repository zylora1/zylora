# Disaster recovery

Status: **Phase 0 recovery policy frozen; provider-specific commands are completed during deployment**

## Recovery objectives

Provisional production targets, to be validated against selected infrastructure and business impact:

| Asset/service | RPO target | RTO target | Recovery basis |
| --- | --- | --- | --- |
| PostgreSQL commercial/ownership data | ≤ 5 minutes | ≤ 60 minutes | encrypted PITR + snapshots |
| Public assets/deployment bundles | ≤ 24 hours or zero for versioned writes | ≤ 2 hours | versioned object storage/replication |
| Private Leads/exports/assets | ≤ 24 hours, tighter where provider supports | ≤ 4 hours | encrypted versioned storage + DB metadata |
| Redis cache/transport | no durability promise for cache | ≤ 30 minutes | recreate; outbox re-dispatch |
| FAISS indexes | rebuildable from published source | ≤ 4 hours for active priority sites | manifests/source + reindex |
| Platform application | last approved release | ≤ 30 minutes | immutable images/config |

RPO/RTO are not contractual claims until infrastructure drills prove them. Payments/provider state may
require reconciliation even when local recovery meets RPO.

## Backup design

PostgreSQL uses automated encrypted backups, continuous WAL/PITR where available, daily snapshots,
retention tiers approved for legal/business needs, separate access credentials, and protected deletion.
Backups include schema/migration version and are monitored for freshness/completion. Object storage
uses versioning, lifecycle, encryption, and replication/backup according to data class. Secret-manager
recovery and key escrow/rotation procedures are separate from data backups.

Redis is not authoritative. Durable work intent remains in PostgreSQL outbox. FAISS is derived; store
versioned manifests/artifacts for fast restore but retain ability to rebuild from the exact authorized
published WebsiteVersion and embedding configuration.

A backup is trusted only after automated integrity checks and scheduled isolated restore drills.
Quarterly full drills are the initial target; critical migration/release changes may require an extra
pre/post drill.

## Restore validation checklist

1. Restore into an isolated network/account, never over production.
2. Verify backup identity, checksum, encryption access, timestamp, migration version and expected RPO.
3. Start with outbound provider/email/domain/payment effects disabled.
4. Run schema and critical invariants: roles, ownership, one-live, four plans, payments/exports,
   Lead-credit, Template approval, FAISS manifests.
5. Reconcile object references/checksums and identify missing versions.
6. Run authentication with isolated accounts, core API reads, deployment artifact health, and job
   outbox counts without sending external effects.
7. Select cutover point, rotate/validate secrets, fence old primary, update endpoints, then enable
   workers/providers in controlled order.
8. Reconcile payments/webhooks, queues, domains, deployments, emails and analytics watermarks.
9. Run post-recovery browser/security smoke and document measured RPO/RTO/data impact.

## Scenarios

### Database corruption or regional loss

- Detect: integrity/query errors, replication/backup alarms, invariant failures.
- Contain: stop writes or isolate affected primary; preserve evidence; pause external-effect workers.
- Recover: choose clean PITR point, restore isolated, validate, fence old primary, controlled cutover.
- Impact: writes after recovery point require reconciliation; provider payments and received Leads may
  exist externally and must be re-ingested/reconciled without duplication.
- Validate: full invariant suite, provider reconciliation, object references and critical journeys.

### Accidental deletion or bad data command

- Detect via audit/invariant/customer report.
- Disable responsible command/account; do not run ad-hoc inverse SQL.
- Prefer domain-level restoration from immutable history/version/object version. For broad damage use
  point-in-time copy and selectively reapply through audited repair tools or full PITR decision.
- Verify current ownership, billing, credits, routes and access epochs after recovery.

### Failed release or bad migration

- Stop promotion/canary; preserve logs and migration evidence.
- Roll back immutable app images only if schema remains backward compatible. Otherwise use documented
  forward-fix or tested migration downgrade.
- Restore DB only when data impact justifies it and provider/external effects are fenced/reconciled.
- Customer Website deployments remain on their last known-good active versions.

### Redis or worker outage

- API marks affected capabilities degraded and fails closed where rate-limit/safety requires.
- Replace Redis/worker capacity; rebuild cache; dispatch pending PostgreSQL outbox events.
- Idempotent tasks tolerate duplicates and expired leases; monitor backlog/dead letters and provider
  rate limits during recovery.
- Validate no duplicate payment, Lead-credit, notification, campaign, export, deployment or index effect.

### Object storage outage or loss

- Preserve DB metadata; stop uploads/build/export/index operations from claiming success.
- Fail over only to a configured consistent replica; otherwise wait/recover provider and verify
  checksum/version references.
- Restore missing objects from version/replica/backup. Expired exports may be regenerated only after
  ownership and trusted payment recheck. Published routes stay on cached/known-good assets where safe.

### DNS/Cloudflare outage

- Do not mark new domains active or Websites published without verification.
- Preserve current known-good routing; queue bounded idempotent retries and surface provider status.
- On recovery reconcile hostname/TLS/route state before transitions. Never blindly recreate/delete
  ambiguous hostnames.

### Payment webhook/provider outage

- Keep checkouts/payments pending; never grant capability from browser return.
- Store verifiable incoming events when possible, pause unsafe retries, and use provider reconciliation
  after recovery with stable references/idempotency.
- Compare amount/currency/purpose and quarantine conflicts. Notify Users honestly about pending state.

### Email provider outage

- Core transaction (Lead, transfer, payment, account security request state) remains durable.
- Queue retry with bounds; switch provider only through an approved adapter/runbook that preserves
  message idempotency and suppression.
- Security verification flows show delay and prevent uncontrolled resend storms.

### Deployment failure

- New build occurs beside current live deployment. Failure never changes active pointer.
- Capture safe logs, mark attempt failed, release reservations where appropriate, and offer retry.
- If a bad switch occurs, route to the previous verified artifact and health-check; separately repair
  underlying build/config.

### Compromised secret/session

- Identify scope/version and revoke/rotate in dependency order; increment affected auth/access epochs.
- Invalidate sessions, signed URLs/site tokens/provider credentials as scoped; inspect audit/provider
  evidence and suspend high-risk operations.
- Redeploy clean configuration, verify no secret in logs/builds/ZIPs, reconcile unauthorized actions,
  and follow applicable incident notification policy.

### FAISS corruption or isolation concern

- Disable affected chatbot/index immediately; published Website and Lead forms remain available.
- Remove active pointer, preserve evidence, verify source published version/owner/access epoch, rebuild
  into a new prefix, run checksum/isolation/search tests, then atomically activate.
- A suspected cross-tenant result is a security incident requiring scope analysis, not a normal reindex.

## Operational controls

- Backup/restore permissions are separate from ordinary deploy/admin access.
- Break-glass access is time-bound, approved, logged, and reviewed.
- Runbooks include exact provider commands only after providers are selected; examples never contain
  real account IDs/secrets.
- Drills capture date, scenario, backup age, measured RPO/RTO, invariant/browser results, failures,
  owner, remediation and next drill.
- Post-incident work fixes the common abstraction and adds automated detection/regression.
