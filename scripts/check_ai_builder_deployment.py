from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Literal
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import boto3
import httpx
from botocore.config import Config as BotoConfig
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from zylora_api.core.config import Settings
from zylora_api.db.session import normalize_async_database_url

EXPECTED_MIGRATION = "20260823_0018"
SECRET_NAMES = frozenset(
    {
        "AUTH_SECRET",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
        "AI_BUILDER_SERVICE_TOKEN",
        "AI_BUILDER_PROVIDER_TOKEN",
        "AI_BUILDER_SANDBOX_TOKEN",
        "OPENAI_API_KEY",
        "GOOGLE_CLIENT_SECRET",
        "TURNSTILE_SECRET_KEY",
        "CLOUDFLARE_API_TOKEN",
    }
)
AI_REQUIRED_NAMES = (
    "ENVIRONMENT",
    "DATABASE_URL",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "AUTH_SECRET",
    "STORAGE_PROVIDER",
    "S3_REGION",
    "S3_BUCKET",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "WEB_ORIGINS",
    "ADMIN_ORIGIN",
    "TRUSTED_HOSTS",
    "COOKIE_SECURE",
    "AI_BUILDER_ENABLED",
    "AI_BUILDER_ROLLOUT_MODE",
    "AI_BUILDER_PREVIEW_ORIGIN",
    "AI_BUILDER_URL",
    "AI_BUILDER_SERVICE_TOKEN",
    "AI_BUILDER_ENVIRONMENT",
    "AI_BUILDER_PROVIDER_URL",
    "AI_BUILDER_PROVIDER_TOKEN",
    "AI_BUILDER_PROVIDER_NAME",
    "AI_BUILDER_PROVIDER_MODEL",
    "AI_BUILDER_SANDBOX_URL",
    "AI_BUILDER_SANDBOX_TOKEN",
)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: Literal["pass", "fail", "not_run"]
    detail: str


def _present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _safe_missing_names() -> list[str]:
    return [name for name in AI_REQUIRED_NAMES if not _present(name)]


def _is_remote_tls(value: str, schemes: tuple[str, ...]) -> bool:
    lowered = value.casefold()
    return lowered.startswith(schemes) and not any(
        marker in lowered for marker in ("localhost", "127.0.0.1", "::1")
    )


def _postgres_tls(value: str) -> bool:
    if not _is_remote_tls(value, ("postgresql+psycopg://", "postgresql://")):
        return False
    normalized = value.replace("postgresql+psycopg://", "postgresql://", 1)
    query = parse_qs(urlparse(normalized).query)
    sslmode = query.get("sslmode", [""])[0].casefold()
    ssl = query.get("ssl", [""])[0].casefold()
    return sslmode in {"require", "verify-ca", "verify-full"} or ssl in {"1", "true"}


async def _database_check(settings: Settings) -> Check:
    engine = create_async_engine(
        normalize_async_database_url(settings.database_url),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
        connect_args={
            "options": (
                f"-c statement_timeout={settings.database_statement_timeout_ms} "
                f"-c lock_timeout={settings.database_lock_timeout_ms}"
            )
        },
    )
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            statement_timeout = str(await connection.scalar(text("SHOW statement_timeout")))
            lock_timeout = str(await connection.scalar(text("SHOW lock_timeout")))
        if revision != EXPECTED_MIGRATION:
            return Check("postgresql", "fail", "migration head does not match the release")
        if statement_timeout in {"0", "0ms"} or lock_timeout in {"0", "0ms"}:
            return Check("postgresql", "fail", "database safety timeouts are not active")
        return Check("postgresql", "pass", "reachable; migration and session timeouts verified")
    except Exception:
        return Check("postgresql", "fail", "connection or schema verification failed")
    finally:
        await engine.dispose()


async def _redis_check(name: str, url: str) -> Check:
    client = Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
    try:
        ready = bool(await client.ping())
        return Check(name, "pass" if ready else "fail", "reachable" if ready else "ping failed")
    except Exception:
        return Check(name, "fail", "connection failed")
    finally:
        await client.aclose()


async def _builder_check(settings: Settings) -> Check:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0),
            follow_redirects=False,
        ) as client:
            response = await client.get(
                f"{settings.ai_builder_url.rstrip('/')}/readiness",
                headers={"Authorization": f"Bearer {settings.ai_builder_service_token}"},
            )
        if response.status_code != 200:
            return Check("builder", "fail", "readiness rejected or a dependency is unavailable")
        payload = response.json()
        if payload.get("status") != "ready":
            return Check("builder", "fail", "readiness response is not ready")
        return Check("builder", "pass", "authenticated readiness passed")
    except Exception:
        return Check("builder", "fail", "readiness connection or response validation failed")


def _s3_client(settings: Settings):  # type: ignore[no-untyped-def]
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=BotoConfig(
            s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"}
        ),
    )


def _storage_check(settings: Settings, allow_write_probe: bool) -> Check:
    client = _s3_client(settings)
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
        versioning = client.get_bucket_versioning(Bucket=settings.s3_bucket)
        if versioning.get("Status") != "Enabled":
            return Check("artifact_storage", "fail", "bucket versioning is not enabled")
        try:
            policy = client.get_bucket_policy_status(Bucket=settings.s3_bucket)
            if bool(policy.get("PolicyStatus", {}).get("IsPublic")):
                return Check("artifact_storage", "fail", "bucket policy is public")
        except Exception:
            return Check("artifact_storage", "fail", "private bucket policy could not be proven")
        if not allow_write_probe:
            return Check(
                "artifact_storage",
                "not_run",
                "read checks passed; immutable write/read/delete probe was not authorized",
            )
        key = f"deployment-preflight/{uuid4()}.bin"
        payload = os.urandom(64)
        digest = sha256(payload).hexdigest()
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=payload,
            ContentType="application/octet-stream",
            Metadata={"sha256": digest, "purpose": "deployment-preflight"},
            ServerSideEncryption="AES256",
            IfNoneMatch="*",
        )
        response = client.get_object(Bucket=settings.s3_bucket, Key=key)
        downloaded = bytes(response["Body"].read())
        if downloaded != payload or response.get("Metadata", {}).get("sha256") != digest:
            return Check("artifact_storage", "fail", "write probe integrity verification failed")
        client.delete_object(Bucket=settings.s3_bucket, Key=key)
        return Check(
            "artifact_storage", "pass", "private versioned bucket and integrity probe passed"
        )
    except Exception:
        return Check("artifact_storage", "fail", "bucket configuration or storage probe failed")


async def run(
    target: str,
    allow_write_probe: bool,
    activation_state: Literal["disabled", "canary"] = "disabled",
) -> tuple[str, list[Check]]:
    missing = _safe_missing_names()
    if missing:
        return "blocked", [
            Check("configuration", "fail", f"missing variables: {', '.join(missing)}")
        ]
    try:
        settings = Settings(_env_file=None)
    except ValidationError:
        return "blocked", [
            Check("configuration", "fail", "typed production configuration validation failed")
        ]
    checks: list[Check] = []
    if settings.environment != target:
        checks.append(Check("environment", "fail", "runtime environment does not match target"))
    else:
        checks.append(Check("environment", "pass", f"explicit {target} environment"))
    if os.environ.get("AI_BUILDER_ENVIRONMENT") != target:
        checks.append(
            Check("builder_environment", "fail", "Builder environment does not match target")
        )
    else:
        checks.append(
            Check("builder_environment", "pass", f"explicit {target} Builder environment")
        )
    if activation_state == "disabled":
        if settings.ai_builder_enabled:
            checks.append(
                Check(
                    "feature_flag", "fail", "AI_BUILDER_ENABLED must remain false before activation"
                )
            )
        else:
            checks.append(
                Check("feature_flag", "pass", "server-side feature flag remains disabled")
            )
        if settings.ai_builder_rollout_mode != "canary" or settings.ai_builder_canary_users:
            checks.append(
                Check(
                    "canary_scope",
                    "fail",
                    "predeployment requires canary mode with an empty User allowlist",
                )
            )
        else:
            checks.append(Check("canary_scope", "pass", "canary mode is empty before activation"))
    else:
        if not settings.ai_builder_enabled:
            checks.append(Check("feature_flag", "fail", "AI_BUILDER_ENABLED is not true"))
        else:
            checks.append(Check("feature_flag", "pass", "server-side feature flag enabled"))
        if settings.ai_builder_rollout_mode != "canary" or not settings.ai_builder_canary_users:
            checks.append(
                Check("canary_scope", "fail", "enabled canary requires explicit User IDs")
            )
        else:
            checks.append(
                Check("canary_scope", "pass", "server-authoritative User canary configured")
            )
    if target in {"staging", "production"}:
        if not _postgres_tls(settings.database_url):
            checks.append(
                Check("database_transport", "fail", "remote TLS PostgreSQL was not proven")
            )
        if not all(
            _is_remote_tls(url, ("rediss://",))
            for url in (
                settings.redis_url,
                settings.celery_broker_url,
                settings.celery_result_backend,
            )
        ):
            checks.append(
                Check(
                    "redis_transport",
                    "fail",
                    "staging/production Redis endpoints require TLS",
                )
            )
        protected_urls = {
            "Builder": settings.ai_builder_url,
            "provider": os.environ.get("AI_BUILDER_PROVIDER_URL", ""),
            "sandbox": os.environ.get("AI_BUILDER_SANDBOX_URL", ""),
            "preview": settings.ai_builder_preview_origin,
        }
        for component, value in protected_urls.items():
            if not _is_remote_tls(value, ("https://",)):
                checks.append(
                    Check(
                        f"{component.casefold()}_transport",
                        "fail",
                        f"{component} endpoint requires remote HTTPS",
                    )
                )
        tokens = [
            settings.ai_builder_service_token or "",
            os.environ.get("AI_BUILDER_PROVIDER_TOKEN", ""),
            os.environ.get("AI_BUILDER_SANDBOX_TOKEN", ""),
        ]
        if any(len(value) < 32 for value in tokens) or len(set(tokens)) != 3:
            checks.append(
                Check(
                    "service_tokens",
                    "fail",
                    "service tokens must be distinct and at least 32 characters",
                )
            )
        if not os.environ.get("AI_BUILDER_PROVIDER_NAME", "").strip():
            checks.append(Check("provider_identity", "fail", "provider identity must be explicit"))

        if (
            not settings.cookie_secure
            or not settings.allowed_origins
            or any(not _is_remote_tls(origin, ("https://",)) for origin in settings.allowed_origins)
            or not _is_remote_tls(settings.admin_origin, ("https://",))
            or any(
                host in {"*", "localhost", "127.0.0.1", "testserver"}
                for host in settings.allowed_hosts
            )
        ):
            checks.append(
                Check(
                    "edge_origin",
                    "fail",
                    "secure explicit origins, cookies, and trusted hosts are required",
                )
            )
        if settings.ai_builder_preview_origin.rstrip("/") in {
            *(origin.rstrip("/") for origin in settings.allowed_origins),
            settings.admin_origin.rstrip("/"),
        }:
            checks.append(Check("preview_origin", "fail", "preview origin must be dedicated"))
        if settings.s3_endpoint_url and not _is_remote_tls(settings.s3_endpoint_url, ("https://",)):
            checks.append(
                Check(
                    "storage_transport",
                    "fail",
                    "object storage endpoint requires remote HTTPS",
                )
            )
    checks.extend(
        await asyncio.gather(
            _database_check(settings),
            _redis_check("redis", settings.redis_url),
            _redis_check("celery_broker", settings.celery_broker_url),
            _redis_check("celery_result_backend", settings.celery_result_backend),
            _builder_check(settings),
        )
    )
    checks.append(await asyncio.to_thread(_storage_check, settings, allow_write_probe))
    status = (
        "ready_for_staging_validation"
        if all(item.status == "pass" for item in checks)
        else "blocked"
    )
    return status, checks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed, secret-safe AI Builder deployment preflight."
    )
    parser.add_argument("--target", choices=("staging", "production"), required=True)
    parser.add_argument(
        "--activation-state",
        choices=("disabled", "canary"),
        default="disabled",
        help="Expected server-side rollout state for this preflight.",
    )
    parser.add_argument(
        "--allow-storage-write-probe",
        action="store_true",
        help="Write, verify, and delete one random object under deployment-preflight/.",
    )
    args = parser.parse_args()
    status, checks = asyncio.run(
        run(args.target, args.allow_storage_write_probe, args.activation_state)
    )
    print(
        json.dumps(
            {
                "target": args.target,
                "activation_state": args.activation_state,
                "status": status,
                "checks": [asdict(item) for item in checks],
                "secrets_printed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "ready_for_staging_validation" else 1


if __name__ == "__main__":
    raise SystemExit(main())
