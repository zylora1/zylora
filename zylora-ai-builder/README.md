# Zylora AI Builder

Stateless, isolated orchestration for AI-generated business websites. It is not a browser dependency, is never imported by `apps/web` or `apps/api`, and does not own authoritative job state.

## Boundary

Zylora Core owns authentication, authorization, encrypted prompts, projects, immutable generation versions, leased jobs, quotas, artifacts metadata, previews, billing, domains, publishing, transfer, and export. A Core worker decrypts a prompt only after obtaining a PostgreSQL lease, then invokes this service with a stable generation ID and idempotency key.

This service calls a provider-neutral generation adapter, validates and scans the returned constrained Next.js file map, and submits fixed checks to a separately deployed sandbox. The sandbox uploads a content-addressed archive to private object storage. The service returns artifact metadata; Core independently verifies the stored bytes and records completion. This service has no publish API.

## Endpoints

- `GET /liveness`: process responsiveness only.
- `GET /readiness`: fail-closed configuration and provider/sandbox dependency checks.
- `GET /health`: readiness-compatible sanitized health result.
- `POST /v1/generations/{generation_id}/execute`: authenticated, synchronous, idempotent execution. Authoritative lifecycle state remains in Core PostgreSQL.

The request and response schemas are private service contracts. Prompts are never logged or returned.

## Configuration

Required when enabled:

- `AI_BUILDER_ENVIRONMENT`: `development`, `test`, `staging`, or `production`.
- `AI_BUILDER_SERVICE_TOKEN`: Core-to-builder bearer token, at least 32 characters.
- `AI_BUILDER_PROVIDER_URL`, `AI_BUILDER_PROVIDER_TOKEN`, `AI_BUILDER_PROVIDER_NAME`, `AI_BUILDER_PROVIDER_MODEL`.
- `AI_BUILDER_SANDBOX_URL`, `AI_BUILDER_SANDBOX_TOKEN`.
- `AI_PROVIDER_CONNECT_TIMEOUT_SECONDS`, `AI_PROVIDER_TIMEOUT_SECONDS`, `AI_PROVIDER_MAX_RETRIES`.
- `MAX_AI_PROMPT_BYTES`, `MAX_AI_OUTPUT_TOKENS`.
- `AI_SANDBOX_TIMEOUT_SECONDS`, `AI_SANDBOX_MAX_ARTIFACT_BYTES`.
- `PORT` (default `8090`).

Production requires HTTPS provider/sandbox URLs and refuses incomplete or unsafe configuration. There is no automatic fake provider, local sandbox, in-process job registry, or filesystem artifact fallback.

## Generated-source contract

The provider returns source only, not shell commands. Validation enforces normalized relative paths, text-only approved extensions, file-count/file-size/total-size bounds, no `package.json`, no lifecycle scripts, no binary payloads, and scanning for process execution, environment/credential access, filesystem escape, arbitrary networking, internal metadata endpoints, dynamic evaluation, and unsupported runtimes.

## Sandbox contract

The fixed sandbox profile uses the pinned `zylora-next-v1` runtime, no network, no install commands or lifecycle scripts, one CPU, 512 MiB memory, 128 PIDs, an execution timeout, read-only root, disposable workspace/tmpfs, dropped capabilities, no-new-privileges, and an empty platform-secret environment. It performs fixed typecheck, build, browser, accessibility, SEO, and artifact-scan checks before uploading an immutable `.tar.gz` archive under:

```text
ai-sites/{owner_user_id}/{project_id}/{generation_id}/{sha256}.tar.gz
```

Core verifies that prefix, content type, size, and SHA-256 before accepting completion.

## Local checks

```powershell
npm run check
```

Starting the service without provider and sandbox configuration is safe: liveness remains available, readiness is degraded, and execution fails closed. See `docs/operations/AI_BUILDER.md` for activation and recovery.