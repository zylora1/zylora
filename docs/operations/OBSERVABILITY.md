# Observability and operational health

Status: **Phase 0 signal contract frozen**

## Correlation

Every HTTP request, domain command, outbox event, worker job, provider request/webhook, deployment,
payment, transfer, export, and Lead operation carries a validated/generated correlation ID. Stable
domain operation/event/idempotency IDs complement—not replace—it. Browser errors may display the safe
correlation/reference ID for support.

## Structured logs

JSON logs include timestamp, level, service/version/environment, correlation/request/job ID, route or
event type, safe resource type/opaque ID, state transition, latency, attempt, outcome and stable error
code. A centralized serializer redacts cookies/auth, passwords, OTP/reset/session/OAuth tokens,
provider/payment secrets, signed URLs, raw Lead/conversation content where unnecessary, and encryption
material. Production stack traces go only to protected error telemetry.

## Metrics

Platform metrics:

- HTTP rate/error/latency by safe route/status; DB pool/query/transaction conflicts; Redis health;
- outbox age, queue depth, job latency/retry/dead-letter by task type;
- auth success/failure/lock/challenge rates without account enumeration;
- upload rejection/processing, storage error/capacity/lifecycle backlog;
- payment checkout/webhook/signature/replay/reconciliation/failure and pending age;
- deployment duration/failure/rollback/current-live health; domain verification/TLS/provider error;
- FAISS build/query latency/failure/cache/checksum/isolation rejection and stale-index age;
- Lead accepted/rejected/idempotent duplicate/credit failure and invariant reconciliation;
- email/campaign accepted/delivered/bounce/complaint/suppression/retry;
- AI/embedding call/usage/latency/failure/estimated cost by safe product operation;
- analytics ingestion/aggregation lag and dropped-invalid events.

Business dashboards read canonical aggregates and never replace technical monitoring or fabricate
data. Metrics labels avoid User/Website/email/domain as unbounded dimensions.

## Traces and provider evidence

Distributed traces cover API → DB/outbox → worker → provider/storage with sampling that retains errors
and high-value commercial workflows. Trace attributes are redacted and bounded. Provider raw evidence
is stored only where required, encrypted/private with retention; logs reference its hash/record.

## Health endpoints

`/liveness` reports process responsiveness only. `/readiness` checks required database connectivity,
migration compatibility, and ability to serve the process role. Redis or optional provider degradation
is reported as structured component health and makes readiness fail only when the role cannot operate
safely—for example a worker without queue transport or an API endpoint that cannot enforce required
abuse controls.

Super Admin System Health consumes sanitized current checks and recent incident signals; it exposes no
credentials, internal network layout, or raw stack traces.

## Alerts and SLO direction

Initial SLOs are baselined in staging/early production and approved before launch. Alert on symptoms
with action: sustained API error/latency, readiness loss, DB saturation/replication/backup failure,
old outbox/queue backlog, dead letters, payment signature/replay/conflict spikes, pending payment/export
age, failed deployment/live health, domain/TLS regression, Lead-credit invariant mismatch, cross-tenant
security rejection spike, email complaint/bounce, storage lifecycle failure, and secret/security events.

Every page/alert has severity, owner, deduplication, runbook link, user impact, and escalation. Avoid
alerts on every retry or optional-provider blip.

## Operational invariant checks

Scheduled read-only/repair-gated checks report:

- account enum values and exactly one active Super Admin;
- one open ownership per non-deleted Website;
- no duplicate `live_owner_user_id` and lifecycle/live marker consistency;
- current public plan catalog contains exactly four valid plans;
- trusted Payment matches payable amount/currency/purpose;
- READY exports have trusted payment and valid private artifact; account exports have no deployable
  manifest;
- every captured Lead has exactly one `-1` ledger entry and cached balance matches ledger;
- active FAISS manifest Website/owner/version/checksum matches database;
- only approved/validated Template versions are publicly referenced;
- audit/outbox/job retention and dead-letter health.

Checks never silently mutate commercial/ownership data. Repair is an explicit domain command with
preview, reason, audit, backup/rollback and authorization.

## Dashboards

Operations dashboards separate service health, customer publishing/domains, payments/subscriptions,
Leads/credits/chatbot, email/campaigns, storage/backups, and security. Release annotations connect
regressions to code/config/migration versions. User-facing analytics is a separate privacy-aware
product surface based only on real events.

## AI Builder signals

`AiGenerationEvent` is the durable, prompt-free transition evidence. Structured API/worker/builder logs attach bounded correlation, job, project, generation, worker, attempt, state, duration, provider/model identifier, artifact size, outcome, and stable error category fields. Prompt text, encrypted prompt bytes, service tokens, signed URLs, and provider response bodies are prohibited.

The existing metrics/log pipeline should derive `ai_generation_requested_total`, `ai_generation_completed_total`, `ai_generation_failed_total`, `ai_generation_cancelled_total`, `ai_generation_retry_total`, `ai_generation_duration_seconds`, `ai_generation_queue_delay_seconds`, `ai_provider_error_total`, `ai_sandbox_build_failed_total`, and `ai_artifact_bytes`. IDs are trace fields, never unbounded metric labels. Alert on readiness loss, old ID-only outbox events, expired running leases, exhausted retries, and artifact checksum/storage failures. The recovery and kill-switch procedures are in `docs/operations/AI_BUILDER.md`.