# Local development

Status: **Phase 3 complete design system and portal shells**

Cloudflare Turnstile and WAF are the approved abuse boundary. `.env.example` uses Cloudflare's
documented public test keys for local validation; production rejects those keys. Local email/password,
Google adapter configuration, sessions, throttling, audit, and User/Admin surfaces are executable.

Phase 3 adds the shared `packages/ui` visual system plus the responsive `/app` and isolated Admin
shells. `npm run test:e2e` now includes exact-width WCAG, keyboard, reduced-motion, overflow,
loading/error, and no-fake-analytics browser audits; their screenshots remain uncommitted test artifacts.

## Prerequisites

- Node.js `24.11.0` and npm `11.6.1`
- Python `3.13.13`
- uv `0.11.17`
- Docker Desktop with Compose

The repository pins JavaScript and Python dependencies in `package-lock.json` and `uv.lock`.
Permanent customer artifacts must not be written to local application disks.

## Clean setup

```powershell
npm ci
uv sync --all-packages --frozen --link-mode copy
Copy-Item .env.example .env
npm run infra:up
npm run migrate
```

The example environment contains development-only credentials. Production startup rejects local
endpoints, development credentials, disabled object storage, insecure cookies/origins, missing Google
OIDC credentials, and missing SMTP delivery.

Compose starts PostgreSQL, Redis, MinIO, and Mailpit. Mailpit accepts SMTP on `localhost:1025` and its
local inbox is available at `http://localhost:8025`.

## Authentication configuration

Email/password delivery uses the configured SMTP server; it never reports a fake delivery success.
The local `.env.example` points at Mailpit. `API_INTERNAL_URL` is server-only; browsers call the
same-origin `/api/v1` proxy so User and Admin cookies remain host-only. For Google sign-in,
register the exact callback
`http://localhost:3000/api/v1/auth/google/callback`, then set `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET` in the uncommitted `.env` file.

`TRUSTED_PROXY_IPS` is empty by default. Add only immediate reverse-proxy IP addresses that sanitize
`X-Forwarded-For`; client-supplied forwarding headers are otherwise ignored.

Bootstrap the one Super Admin exactly once after migration:

```powershell
$env:ZYLORA_BOOTSTRAP_ADMIN_EMAIL='admin@example.com'
$env:ZYLORA_BOOTSTRAP_ADMIN_PASSWORD='replace-with-a-strong-unique-password'
$env:ZYLORA_BOOTSTRAP_ADMIN_NAME='Zylora Super Admin'
npm run bootstrap:super-admin
Remove-Item Env:ZYLORA_BOOTSTRAP_ADMIN_EMAIL
Remove-Item Env:ZYLORA_BOOTSTRAP_ADMIN_PASSWORD
Remove-Item Env:ZYLORA_BOOTSTRAP_ADMIN_NAME
```

The command refuses to run when a Super Admin already exists or the email is already owned. Never put
bootstrap credentials in `.env.example`, source control, shell scripts, or command arguments.
Production readiness requires exactly one active `SUPER_ADMIN` with a Super Admin profile.

## Run the application boundaries

Use three terminals:

```powershell
npm run dev:web
npm run dev:api
npm run dev:worker
```

Web runs on `http://localhost:3000`, the isolated Admin host is
`http://admin.localhost:3000`, and API runs on `http://127.0.0.1:8000`. The local Celery worker uses
the cross-platform solo pool; that is a development choice, not a production worker topology.

Operational endpoints:

- API liveness: `http://127.0.0.1:8000/liveness`
- API readiness: `http://127.0.0.1:8000/readiness`
- API version: `http://127.0.0.1:8000/version`
- Web health: `http://localhost:3000/health`

## Phase 6 AI provider

AI editing is fail-closed and disabled by default. Manual editing, previews, Page Manager, and
revision restore continue to work without a provider. To exercise the real adapter locally, set
server runtime values only:

```powershell
$env:AI_PROVIDER='openai'
$env:OPENAI_API_KEY='retrieve-from-your-secret-manager'
$env:OPENAI_MODEL='gpt-5.6-terra'
npm run dev:api
Remove-Item Env:OPENAI_API_KEY
```

Never prefix the key with NEXT_PUBLIC, expose it to the Web process, place it in repository files, or
log prompts/credentials. Production validates the official OpenAI API base URL and requires the key.

## Quality and test commands

```powershell
npm run format
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run test:integration
npm run build
npm run test:e2e
npm run security
npm run contracts:generate
npm run contracts:check
npm run migrate:check
```

`npm run test` includes Web tests and the branch-aware Python unit/integration coverage suite. Healthy
PostgreSQL, Redis, and Mailpit services plus the applied migration are therefore required.
`npm run test:e2e` starts the previously built production Web server on port `3100`; run
`npm run build:web` first. `npm run security` audits npm and third-party Python dependencies and scans
maintained source for deleted architecture and required-functionality placeholders.

## Database migration round-trip

For an isolated local test database:

```powershell
uv run --package zylora-api alembic -c apps/api/alembic.ini downgrade base
npm run migrate
npm run migrate:check
```

Never run a downgrade against shared staging or production data without an approved release plan.

## Stop local infrastructure

```powershell
npm run infra:down
```

Compose preserves named PostgreSQL, Redis, MinIO, and Mailpit volumes. Remove volumes only as an
explicit, separately approved destructive action.
