# Local development

Status: **Phase 1 executable foundation**

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
endpoints, development credentials, disabled object storage, and non-HTTPS origins.

## Run the application boundaries

Use three terminals:

```powershell
npm run dev:web
npm run dev:api
npm run dev:worker
```

Web runs on `http://localhost:3000`, API on `http://127.0.0.1:8000`, and the local Celery worker uses
the cross-platform solo pool. The solo pool is a local-development choice, not a production worker
topology.

Operational endpoints:

- API liveness: `http://127.0.0.1:8000/liveness`
- API readiness: `http://127.0.0.1:8000/readiness`
- API version: `http://127.0.0.1:8000/version`
- Web health: `http://localhost:3000/health`

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

`npm run test:e2e` starts the previously built production Web server on port `3100`; run
`npm run build:web` first. Integration tests require healthy PostgreSQL and Redis services and an
applied migration. `npm run security` audits npm and third-party Python dependencies and scans
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

Compose preserves named PostgreSQL, Redis, and MinIO volumes. Remove volumes only as an explicit,
separately approved destructive action.
