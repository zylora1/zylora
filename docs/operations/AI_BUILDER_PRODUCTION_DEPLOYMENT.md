# AI Builder production deployment and activation

This document is the deployment authority for the isolated AI Builder. It complements
`AI_BUILDER.md`; it does not change the application architecture. Production activation is an
operations decision and remains fail-closed until every evidence item below is recorded.

## Deployment topology and trust boundaries

```text
Internet
  |
Cloudflare edge/WAF/rate limits
  |
Next.js Web  ---- browser receives no platform service credentials
  |
Zylora Core API
  +-- PostgreSQL (authoritative projects, generations, jobs, leases, events, outbox)
  +-- Redis (transient cache and Celery transport)
  +-- S3-compatible private artifact bucket
  |
Celery worker/beat ---- sends an authenticated ID-scoped execution request
  |
Builder service (private ingress; no database, Redis, billing, OAuth, or Cloudflare secrets)
  +-- approved AI provider (outbound HTTPS only)
  +-- isolated sandbox service (private authenticated endpoint)
        +-- fixed Next.js runtime and dependency profile
        +-- network disabled for generated workloads
        +-- direct least-privilege artifact upload only
```

Deploy Core, worker/beat, Builder, and sandbox as separate workloads and identities. Generated code
runs only in the sandbox workload. Builder ingress accepts Core/worker traffic only; sandbox ingress
accepts Builder traffic only. The sandbox workload must be unable to route to PostgreSQL, Redis,
Core, Builder management endpoints, cloud metadata services, loopback, link-local, RFC1918, or IPv6
local/private ranges. Its artifact credential is restricted to immutable
`ai-sites/<owner>/<project>/<generation>/` writes and cannot list or read unrelated objects.

Cloudflare exposes Web and the intended public API only. Builder, provider adapters, sandbox, Redis,
PostgreSQL, and object-storage administrative endpoints are not public origins.

## Definitive configuration matrix

| Variable | Classification | Safe default | Staging/production requirement |
| --- | --- | --- | --- |
| `ENVIRONMENT` | deployment configuration | `development` | Explicit `staging` or `production` |
| `DATABASE_URL` | secret/environment-specific | local development DSN | Remote PostgreSQL; TLS required by deployment policy |
| `DATABASE_POOL_SIZE` | deployment configuration | 10 | Size from DB connection budget |
| `DATABASE_MAX_OVERFLOW` | deployment configuration | 20 | Bounded within remaining connection budget |
| `DATABASE_POOL_TIMEOUT_SECONDS` | safe bounded default | 30 | 1â€“120 |
| `DATABASE_POOL_RECYCLE_SECONDS` | safe bounded default | 900 | 60â€“3600 |
| `DATABASE_STATEMENT_TIMEOUT_MS` | safety control | 30000 | Nonzero, 1000â€“120000 |
| `DATABASE_LOCK_TIMEOUT_MS` | safety control | 5000 | Nonzero and shorter than statement timeout |
| `REDIS_URL` | secret/environment-specific | local development | Remote TLS Redis in production |
| `CELERY_BROKER_URL` | secret/environment-specific | local development | Remote TLS Redis in production |
| `CELERY_RESULT_BACKEND` | secret/environment-specific | local development | Remote TLS Redis in production |
| `AUTH_SECRET` | secret | development-only value | Secret manager, at least 32 characters |
| `STORAGE_PROVIDER` | deployment configuration | `disabled` | Exactly `s3` |
| `S3_ENDPOINT_URL` | environment-specific | local MinIO example | Approved private/TLS S3-compatible endpoint |
| `S3_REGION`, `S3_BUCKET` | environment-specific | development values | Private versioned bucket |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | secrets | development examples | Least-privilege secret manager values |
| `S3_FORCE_PATH_STYLE` | provider configuration | true | Match the approved provider |
| `AI_BUILDER_ENABLED` | server kill switch | false | True only after staging and activation review |
| AI_BUILDER_ROLLOUT_MODE | server rollout control | canary | canary with explicit User UUIDs; global only after approved expansion |
| AI_BUILDER_CANARY_USER_IDS | deployment configuration | empty | Required for an enabled staging/production canary; comma-separated User UUIDs |
| `AI_BUILDER_PREVIEW_ORIGIN` | environment-specific security boundary | none | Dedicated remote HTTPS origin, distinct from Web/Admin and without privileged cookie scope |
| `AI_BUILDER_URL` | environment-specific | loopback development | Private HTTPS Builder origin |
| `AI_BUILDER_SERVICE_TOKEN` | secret | none | Distinct 32+ character secret |
| `AI_BUILDER_ENVIRONMENT` | deployment configuration | `development` | Explicit `staging` or `production` |
| `AI_BUILDER_PROVIDER_URL` | environment-specific | none | Approved HTTPS provider adapter |
| `AI_BUILDER_PROVIDER_TOKEN` | secret | none | Distinct 32+ character secret |
| `AI_BUILDER_PROVIDER_NAME`, `AI_BUILDER_PROVIDER_MODEL` | deployment metadata | none | Explicit approved identifiers |
| `AI_BUILDER_SANDBOX_URL` | environment-specific | none | Private HTTPS sandbox endpoint |
| `AI_BUILDER_SANDBOX_TOKEN` | secret | none | Distinct 32+ character secret |

The complete production `Settings` validator also requires the existing OAuth, SMTP, Turnstile,
Cloudflare domain, secure-cookie, exact-origin, trusted-host, and provider configuration. Secret
values never use `NEXT_PUBLIC_` names.

## Bounded generation and queue controls

| Control | Variable or implementation | Default |
| --- | --- | --- |
| Prompt bytes | `MAX_AI_PROMPT_BYTES` | 8192 |
| Prompt characters | request contract | 20â€“2000 |
| Provider output tokens | `AI_BUILDER_MAX_OUTPUT_TOKENS` / `MAX_AI_OUTPUT_TOKENS` | 32000 |
| Provider response bytes | `MAX_AI_PROVIDER_RESPONSE_BYTES` | 3500000 |
| Core-to-Builder timeout | `AI_GENERATION_TIMEOUT_SECONDS` | 420 |
| Provider timeout/retries | `AI_PROVIDER_TIMEOUT_SECONDS`, `AI_PROVIDER_HTTP_RETRIES` | 120 / 2 |
| Provider retry delay | Builder exponential backoff plus jitter | 250 ms base, capped at 4 s |
| Sandbox timeout | `AI_SANDBOX_TIMEOUT_SECONDS` | 240 |
| Artifact bytes | `AI_MAX_ARTIFACT_BYTES`, `MAX_AI_ARTIFACT_BYTES` | 50 MiB |
| Signed artifact URL | `AI_ARTIFACT_URL_TTL_SECONDS` | 300 seconds |
| Active jobs per User | `MAX_ACTIVE_AI_JOBS_PER_USER` | 2 |
| Generations per window | `MAX_AI_GENERATIONS_PER_WINDOW` / `AI_GENERATION_WINDOW_SECONDS` | 10 / hour |
| Attempts | `AI_MAX_RETRIES` | 4 total job attempts |
| Job lease | `AI_JOB_LEASE_SECONDS` | 600 seconds |
| Lease renewal | fixed lease | No heartbeat extension; lease exceeds the 420-second Core request timeout |
| Stale recovery | Celery beat | every 30 seconds |
| Outbox dispatch | Celery beat | every 10 seconds |
| Outbox broker attempts | durable outbox | 10, exponential delay capped at 300 seconds |
| Redis visibility | `CELERY_VISIBILITY_TIMEOUT_SECONDS` | 900 seconds |
| General task limits | `CELERY_SOFT_TIME_LIMIT_SECONDS`, `CELERY_TIME_LIMIT_SECONDS` | 270 / 300 |
| AI task limits | `AI_GENERATION_SOFT_TIME_LIMIT_SECONDS`, `AI_GENERATION_TIME_LIMIT_SECONDS` | 570 / 600 |
| Prefetch / worker recycle | `CELERY_PREFETCH_MULTIPLIER`, `CELERY_MAX_TASKS_PER_CHILD` | 1 / 50 |

Visibility timeout must exceed every hard task limit. The fixed generation lease must exceed the Core
request timeout. A late completion lacking the current lease token is discarded.

## Secret and service authentication requirements

Core-to-Builder, Builder-to-provider, and Builder-to-sandbox tokens are distinct. Builder compares
the Core bearer token in constant time and rejects missing or malformed authentication. Provider and
sandbox credentials exist only in the Builder workload. Generated workload environment allowlists
are empty. S3, database, Redis, billing, OAuth, Cloudflare, cookie, and service credentials are never
mounted into Builder-generated workspaces.

Do not put authorization headers, prompts, cookies, provider bodies, or secret-bearing URLs into
logs or traces. Queue and outbox records contain only job IDs. Operator correlation uses User,
project, generation, job, worker, attempt, and correlation IDs.

## Preflight and evidence

Run from an environment populated by the target secret manager. The command deliberately ignores the
repository `.env` file and never prints secret values:

```powershell
npm run ai-builder:preflight:staging -- --allow-storage-write-probe
npm run ai-builder:preflight:staging:canary -- --allow-storage-write-probe
npm run ai-builder:preflight:production -- --allow-storage-write-probe
npm run ai-builder:preflight:production:canary -- --allow-storage-write-probe
```

The default preflight proves the safe pre-activation state (`AI_BUILDER_ENABLED=false`, rollout `canary`, empty allowlist). The `:canary` command is a separate post-change gate and proves enabled canary scope with explicit User UUIDs. Neither command authorizes global rollout.

Preflight verifies typed fail-closed configuration, migration head `20260823_0018`, PostgreSQL session
timeouts, Redis/broker/result connectivity, authenticated Builder readiness, private bucket policy,
bucket versioning, and a random integrity-checked storage probe. A successful preflight means only
that infrastructure is ready for staging validation; it is not production activation approval.

Record sanitized evidence: deployment/image digests, migration revision, preflight JSON, readiness
results, test release, secret versions (never values), bucket policy/versioning, network-policy
revision, sandbox runtime profile revision, provider/model approval, and rollback owner.

## Staging activation and failure injection

Use isolated staging PostgreSQL, Redis databases, bucket, provider credentials, sandbox, domains, and
service tokens. Set both environments to `staging`, apply the migration, deploy workloads with
generation disabled, pass readiness and preflight, then enable generation in staging.

Complete one real User journey through queue, provider, sandbox, immutable upload, refresh recovery,
authenticated preview, new-version retry/modification, cancellation, and cross-User denial. Record
that preview completion did not publish a Website.

Inject and verify:

- worker termination and expired-lease reclaim without duplicate completion;
- Builder/API/Celery restarts with durable state retained;
- Redis outage with outbox retention and later dispatch;
- provider 429, 5xx, timeout, malformed/oversized response, and terminal authentication/policy errors;
- sandbox timeout/crash and adversarial filesystem, process, network, metadata, symlink, lifecycle,
  package-manager, fork, memory, and infinite-loop attempts;
- object-storage outage without false `COMPLETED`;
- duplicate submit and duplicate delivery without double generation;
- User B project, generation, retry, cancellation, artifact, and signed-download attempts denied.

The real sandbox evidence must cover IPv4/IPv6 loopback, link-local, RFC1918/private, metadata IPs,
DNS-rebinding targets, `/proc`, `/dev`, absolute and encoded traversal, shell/process tools, and
resource exhaustion. Static scanning is not accepted as sandbox isolation evidence.

## Production activation and rollback

Production activation requires: successful staging evidence, approved production resources,
production migration, image/artifact digests, green Core/Builder/sandbox/provider/storage readiness,
healthy worker and beat, private network policies, observability alerts, backup/restore evidence,
capacity approval, and an on-call rollback owner.

Deploy with `AI_BUILDER_ENABLED=false`; verify the rest of Zylora remains ready. Then change only the
server-side flag to true, canary internal accounts first, verify durable state and metrics, and expand
gradually. Never use a frontend flag as the control.

Rollback is immediate: set `AI_BUILDER_ENABLED=false`, deploy/restart Core and worker roles, stop new
dispatch if necessary, preserve PostgreSQL/outbox/artifacts, and reconcile running leases after the
outage. Do not delete jobs or manually mark them completed. Re-enable only after the failed
dependency and staging/canary evidence are green.
## Canary scope and rapid reversal

The rollout is enforced by Core, not the browser. Keep `AI_BUILDER_ENABLED=false` while deploying.
For staging or the first production cohort, set `AI_BUILDER_ROLLOUT_MODE=canary` and populate
`AI_BUILDER_CANARY_USER_IDS` with explicit internal User UUIDs. Non-allowlisted Users receive the same
stable unavailable response as a disabled deployment; project reads and authorized cancellation remain
available. Removing a User UUID stops new submissions and retries for that User. The fastest global
rollback remains `AI_BUILDER_ENABLED=false`.

`AI_BUILDER_ROLLOUT_MODE=global` is permitted only after the recorded canary evidence, capacity review,
and on-call approval. It is not the environment example default and is never controlled from Next.js.

## Preview and edge boundary

Treat generated preview as hostile content. The artifact-signing API authenticates the User and checks
owner, project, and generation before issuing a short-lived URL. A production preview renderer must use
a dedicated origin with no Zylora session-cookie scope, restrictive CSP, framing policy, no privileged
Core credentials, and no shared CDN caching. Until that origin and its isolation evidence exist, raw
artifact readiness is not approval to expose a public preview. Private AI API and artifact-signing
responses use `Cache-Control: no-store` at the edge.

## Alerting runbook

The existing metrics/log pipeline owns these vendor-neutral alerts. IDs are trace fields, never metric
labels. Initial thresholds are calibrated in staging, recorded with the release, and tightened after
the canary baseline.

| Alert | Signal | Likely causes | First diagnostic action | Mitigation | Escalate when |
| --- | --- | --- | --- | --- | --- |
| Generation failure rate | sustained failed/completed ratio above approved baseline | provider, sandbox, scanner, or storage regression | group safe failure codes by stage and release | pause rollout; disable generation for systemic failures | two windows or customer-visible canary failure |
| Provider outage | readiness loss, provider error rate/latency | provider incident, token expiry, network policy | check Builder readiness and provider status without logging payloads | keep bounded retries; disable generation if sustained | retry exhaustion or provider SLA breach |
| Sandbox outage/denial | sandbox readiness or failure spike | executor crash, capacity, policy change | inspect sandbox health, quota, and policy revision | disable generation; never use local execution fallback | isolation evidence fails or crash loop continues |
| Database outage/saturation | readiness loss, pool timeout, transaction errors | failover, connection exhaustion, lock contention | inspect DB health, pool usage, lock/statement timeout counts | stop new work; preserve leases/outbox; restore DB | failover/backup objective at risk |
| Redis/broker outage | dispatch failures, queue transport readiness | Redis outage, TLS/auth failure | inspect broker connectivity and oldest undispatched outbox age | retain outbox; restore broker; resume idempotent dispatch | backlog exceeds recovery objective |
| Artifact storage outage | upload/sign/checksum failures | credential, bucket, region, or storage incident | verify bucket readiness and safe error category | prevent `COMPLETED`; disable new generation if sustained | integrity or cross-owner concern |
| Queue delay/depth | queue delay or depth above approved capacity | worker loss, provider throttling, workload burst | compare active workers, claims, and oldest queued job | stop rollout expansion; add approved capacity | delay breaches staging-derived SLO |
| Lease expiration | repeated expired RUNNING leases | worker/Builder crash or task timeout mismatch | inspect worker exits and lease/task durations | recover through canonical stale-job task | same job expires repeatedly or duplicates appear |
| Outbox backlog | oldest pending event age/dispatch failures | broker outage or beat failure | inspect beat and ID-only outbox state | restore beat/broker; allow retry-safe dispatch | backlog exceeds recovery objective |
| Worker/Builder crash loop | restart count/readiness loss | bad release, memory limit, dependency failure | inspect safe crash category and image digest | roll back workload; leave feature disabled | rollback does not restore readiness |
| Authorization anomaly | denied cross-owner or service-token spike | attack, stale client, routing exposure | confirm route, source, and opaque resource type | restrict edge/origin; rotate affected service token | any successful unauthorized access is suspected |
| Canary failure | canary journey, error, latency, or isolation gate fails | release or dependency regression | freeze cohort and correlate release evidence | set `AI_BUILDER_ENABLED=false`; preserve history | rollback owner or security incident response required |

## Secret rotation

Never print or copy secret values into release evidence. Record only secret-manager version identifiers.

- Builder service token: deploy Builder accepting the new token during a bounded overlap only if the
  platform supports dual-secret verification; otherwise disable generation, rotate Builder and Core
  together, verify authenticated readiness, then re-enable the canary.
- Provider and sandbox tokens: disable generation, rotate the downstream credential and Builder secret
  reference, verify authenticated dependency readiness, then resume the canary.
- S3 credentials: issue a new least-privilege identity, update Core/sandbox references, run the private
  versioned-bucket integrity probe, revoke the old identity, and verify signing/upload alerts.
- Database and Redis credentials: stop new claims, rotate server and workload references through the
  provider's safe overlap/failover mechanism, verify migrations/outbox/leases, then resume workers.
- `AUTH_SECRET`: follow the authentication key-rotation/session invalidation policy. Do not substitute
  a silent in-place change that leaves ambiguous session validity.

A failed rotation uses the kill switch and workload rollback. Generation history, outbox rows, and
immutable artifacts are never deleted as a rotation or rollback technique.
