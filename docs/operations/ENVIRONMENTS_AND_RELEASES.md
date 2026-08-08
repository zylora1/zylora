# Environments, CI/CD, and release operations

Status: **Phase 0 operational model frozen**

## Environment separation

Development, test, staging, and production use separate PostgreSQL databases, Redis instances/
namespaces, OAuth clients, webhook secrets/endpoints, object-storage buckets/prefixes, encryption keys,
provider accounts/resources, FAISS prefixes, DNS hostnames, monitoring projects, and email sender policy.
No production service depends on a developer workstation or committed local file.

Staging mirrors production topology, TLS/hosts, migrations, workers/queues, object lifecycle, CSP,
cookie/security settings, and provider sandbox behavior closely enough for release evidence. Test and
development may use deterministic adapters; production startup rejects them.

## Configuration classes

| Class | Location | Examples |
| --- | --- | --- |
| Static | source/typed config | supported schema versions, queue names, safe defaults |
| Environment | deployment config | origins, hosts, DB/Redis/storage endpoints, feature enablement |
| Secret | secret manager | session/HMAC/encryption keys, DB/provider credentials |
| Business | versioned PostgreSQL settings | four-plan catalogs, ZIP price, zero-credit policy |

`.env.example` is generated/reviewed as a key-and-description contract with non-secret local examples.
Startup validation rejects missing critical values, weak/default secrets, debug/dev auth in production,
wildcard credentialed CORS, unsafe cookie/host policy, local durable storage, or unapproved adapters.

## CI pipeline

```text
checkout + toolchain verification
→ lockfile/install integrity
→ format check
→ TypeScript/Python typecheck
→ lint
→ unit tests + coverage ratchet
→ generated OpenAPI/client/schema drift check
→ PostgreSQL/Redis integration + fresh migrations
→ security/secret/dependency/license/IaC/container scans
→ Web/API/worker production builds
→ Playwright critical journeys
→ artifact SBOM/provenance/signing
→ protected staging deployment
→ migration + smoke/E2E/accessibility/visual/performance evidence
→ manual approval where required
→ production canary/controlled promotion
→ post-deploy health and invariant checks
```

Known failures block promotion. Protected production jobs consume only immutable artifacts already
tested in staging; they do not rebuild mutable dependencies. Untrusted contributions cannot access
release/provider secrets.

## Migration release policy

Alembic is the only schema-change path. CI proves empty DB → head and previous-release → head. Releases
use expand/migrate/contract for incompatible changes: deploy compatible schema/code, backfill
idempotently with observability, validate constraints/indexes, switch reads/writes, then remove old
shape in a later release.

Before production, record expected locks/runtime, row volume, rollback or forward-fix, backup/PITR
checkpoint, application compatibility, and owner. Destructive operations require explicit approval;
manual schema mutation is an incident, not normal process.

## Deployment strategy

- Web/API/worker images are immutable, versioned by commit and digest, non-root, scanned, and promoted.
- API instances pass liveness/readiness and migration compatibility before traffic.
- Worker releases drain/lease safely; task payload versions support rolling compatibility.
- Web public/Portal/Admin smoke tests cover auth cookies, CSRF, metadata/robots, and critical data reads.
- Rollout starts canary/low percentage when infrastructure supports it; error/latency/invariant alarms
  automatically stop or roll back application promotion.
- Database rollback is separate and only used when explicitly safe. Prefer forward-fix after a
  committed destructive/data migration.

Customer Website deployment/rollback is a separate state machine and never rolls back the Zylora
platform database.

## Release evidence and ownership

Each release records commit/image digests, migration revisions, config version, plan/platform-setting
versions, schema/renderer/template validator versions, tests/scans, staging results, approver,
deployment times, post-deploy checks, and rollback decision. No launch step may exist only in memory.

## Post-deploy verification

- `/liveness`, `/readiness`, version and migration match;
- DB/Redis/storage/queue connections and backlog;
- auth signup/login/logout/session/CSRF smoke in non-production-safe accounts;
- public landing/Templates/Pricing/Blog metadata and no blanket robots block;
- User/Admin isolation and representative authorized/unauthorized API checks;
- worker outbox dispatch and bounded test job;
- provider webhook routing/signature configuration without synthetic paid grant;
- current live Websites/routes remain healthy;
- error/latency/payment/deployment/Lead-credit invariant dashboards remain within thresholds.

## Rollback

Application rollback promotes the previous immutable images/config after compatibility check. Frontend,
API, and worker versions roll together unless their contract window explicitly permits otherwise.
Feature flags may pause newly introduced risky behavior only when documented; they cannot restore
removed V1 roles, portals, editor, or vector/payment providers.

After rollback, verify queues/events created by the newer version remain consumable or pause them,
reconcile ambiguous provider effects, and run invariant checks. Document cause and regression before
retrying release.
