# ADR 026: Durable, isolated AI Next.js generation pipeline

Status: accepted

Date: 2026-08-13

Authority: the user-approved AI Builder production infrastructure amendment

## Context

Zylora's template Website aggregate remains template-first and revisioned. The separately approved AI creation path produces constrained Next.js business-site artifacts. Generated source is untrusted, and neither authoritative job state nor permanent artifacts may live only in a builder process, worker memory, or disposable filesystem.

## Decision

- Core owns `AiSiteProject`, immutable `AiSiteGeneration` versions, leased `AiGenerationJob` executions, immutable `AiGenerationArtifact` metadata, and append-only `AiGenerationEvent` transition evidence in PostgreSQL.
- Submission locks the owner row, validates server-side quotas, encrypts the prompt, creates generation/job state, and inserts an ID-only transactional outbox event in one transaction. Redis/Celery transports work; it is never the source of truth.
- Workers claim jobs with a PostgreSQL row lock and expiring random lease token. Only the current lease may complete or fail a job. Duplicate delivery therefore cannot produce two authoritative completions.
- Stale `RUNNING`, due `RETRY_WAIT`, and undispatched `PENDING` jobs are reconciled by a periodic recovery task. Retries are bounded and use persisted attempts plus backoff. A user retry creates a new linked generation version rather than rewriting history.
- The isolated `zylora-ai-builder` service is stateless. It receives one authenticated execution request, calls a provider-neutral adapter, validates and scans a constrained file map, and submits fixed commands and a fixed dependency profile to a separately authenticated sandbox. It never imports Core code or owns job state.
- The sandbox contract requires an ephemeral isolated executor with no network, bounded CPU/memory/PIDs/time, read-only base, disposable workspace, no platform environment, no lifecycle scripts, and no model-authored shell commands.
- The builder returns only metadata for a content-addressed archive already uploaded to the configured object store. Core downloads it through the storage boundary, verifies owner/project/generation prefix, size, content type, and SHA-256, then records immutable metadata.
- Authenticated preview access is owner-scoped and short-lived. Generation never invokes publication. Any later publishing adapter must enter the existing authoritative publish eligibility and deployment lifecycle.
- Provider, sandbox, broker, storage, and feature activation are configuration boundaries. Production cannot select memory/local/fake implementations. Missing or invalid dependencies make readiness fail and generation remain disabled.

## State and confidentiality

The persisted generation states are `CREATED`, `QUEUED`, `CLAIMED`, `GENERATING`, `VALIDATING`, `SCANNING`, `SANDBOXING`, `BUILDING`, `STORING`, `COMPLETED`, `FAILED`, and `CANCELLED`. Execution rows use `PENDING`, `RUNNING`, `RETRY_WAIT`, `SUCCEEDED`, `FAILED`, and `CANCELLED`.

Prompt plaintext is absent from logs, tracing fields, outbox payloads, Celery payloads, artifacts metadata, and API responses. It is decrypted only by the claimed worker immediately before the authenticated builder request.

## Consequences

A restart of API, worker, or builder does not erase accepted work. Redis loss delays delivery but cannot erase the committed outbox/job. Completed artifacts are versioned, content-addressed, integrity checked, and owner isolated. Cancellation is authoritative but provider termination remains best-effort. An artifact uploaded by an execution that later loses its lease is unreferenced and must be removed by the object-store lifecycle policy, never adopted implicitly.

Production activation remains an operations decision. `AI_BUILDER_ENABLED=false` is the safe default until PostgreSQL migration, durable Redis, S3-compatible storage, isolated builder, approved provider, and hardened sandbox are all ready.