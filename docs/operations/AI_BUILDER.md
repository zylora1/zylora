# AI Builder operations

Status: production-capable, disabled until dependencies are configured

## Runtime boundaries

PostgreSQL is authoritative for projects, immutable generations, leased jobs, artifacts, and transition evidence. The transactional outbox and Redis/Celery provide durable dispatch. `zylora-ai-builder` is stateless and calls only the configured provider and isolated sandbox. The sandbox uploads immutable archives to the configured S3-compatible object store. The builder never publishes a website.

## Safe inspection

Use the application/Super Admin operational surface when available. Read-only SQL is acceptable for incident diagnosis; direct updates are not a normal recovery procedure.

```sql
SELECT state, count(*) FROM ai_generation_jobs GROUP BY state ORDER BY state;
SELECT id, generation_id, state, attempt, max_attempts, retry_at, lease_owner, lease_expires_at, safe_error_code, updated_at
FROM ai_generation_jobs
WHERE state IN ('PENDING', 'RUNNING', 'RETRY_WAIT', 'FAILED')
ORDER BY updated_at;
SELECT generation_id, from_state, to_state, attempt, duration_ms, correlation_id, created_at
FROM ai_generation_events
WHERE generation_id = :generation_id
ORDER BY created_at;
SELECT id, event_type, published_at, attempts, next_attempt_at, lease_owner, leased_until
FROM outbox_events
WHERE aggregate_type = 'AI_GENERATION_JOB'
ORDER BY created_at DESC;
```

Logs may be filtered by correlation ID, job ID, project ID, generation ID, safe state, attempt, or error category. They must never be searched for prompt plaintext because prompts are intentionally absent.

## Recovery

- Stale worker or builder: the periodic `zylora.ai_builder.recover_generation_jobs` task requeues expired leases. A recovered execution uses a new lease token; a late old result cannot commit.
- Broker outage: committed job/outbox rows remain authoritative. Restore Redis/Celery, then the outbox dispatcher publishes eligible ID-only events. Do not recreate requests.
- Provider 429/5xx/timeout: retryable failures enter `RETRY_WAIT` with bounded backoff. Authentication, policy, invalid-request, unsafe-source, and deterministic validation failures are terminal.
- Sandbox outage/timeout: restore the isolated executor. Retryable infrastructure failures recover within the attempt limit. Unsafe or invalid generated projects never run and never retry blindly.
- Artifact-store outage: generation cannot complete without verified durable storage. Restore the bucket/credentials/endpoint and allow the bounded retry/recovery flow. Configure lifecycle expiry for unreferenced `ai-sites/` objects.
- Database outage: stop accepting generation work by readiness/kill switch, restore PostgreSQL, then allow reconciliation. Redis messages alone are not evidence of a job.

If an item exhausts attempts, use the authenticated user retry command when the recorded error is retryable. That command creates a new immutable generation version. Do not reset attempts or states manually.

## Kill switch

Set `AI_BUILDER_ENABLED=false` in the server/worker runtime configuration and deploy/restart the affected roles. Canary scope is server-authoritative through `AI_BUILDER_ROLLOUT_MODE=canary` and `AI_BUILDER_CANARY_USER_IDS`; removing a User prevents new submissions/retries without hiding persisted state. New submissions and retries return the stable unavailable response. Status reads and authorized cancellation remain available. Running isolated executions may finish, but a cancelled or superseded lease cannot commit.

## Re-enable prerequisites

Before setting `AI_BUILDER_ENABLED=true`, verify all of the following:

1. Migration `20260821_0016` is applied to the production PostgreSQL database.
2. Durable Redis broker and Celery worker/beat are healthy.
3. `STORAGE_PROVIDER=s3` points to a private durable bucket with versioning/retention and an unreferenced-object lifecycle policy.
4. Core has a 32+ character service token and an HTTPS builder URL.
5. Builder readiness succeeds with an approved provider adapter and a separately deployed sandbox.
6. Sandbox enforcement includes no network, fixed dependencies, disabled lifecycle scripts, resource/time/PID limits, read-only base, disposable workspace, empty platform-secret environment, and artifact scanning.
7. Provider/output/prompt/concurrency/retry limits have approved values.
8. API, worker, and builder readiness are green; the real staging provider and sandbox lifecycle, failure injection, and ownership-isolation tests in `AI_BUILDER_PRODUCTION_DEPLOYMENT.md` pass.

Never enable generation by frontend flag alone. Never configure a local-memory job registry, local filesystem artifact store, fake provider, or fake sandbox in production.

## Health and signals

- Core `/liveness`: process only.
- Core `/readiness`: PostgreSQL plus required Builder/artifact dependencies when enabled.
- Builder `/liveness`: process only.
- Builder `/readiness` and `/health`: configuration plus provider/sandbox reachability; no secrets are returned.

Derive counters and durations from safe transition events/logs: requested, completed, failed, cancelled, retries, queue delay, total duration, provider errors, sandbox failures, and artifact bytes. Alert on old outbox events, expired running leases, retry exhaustion, readiness loss, and storage-integrity failures.