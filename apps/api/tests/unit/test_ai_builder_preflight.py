from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[4] / "scripts" / "check_ai_builder_deployment.py"
SPEC = importlib.util.spec_from_file_location("check_ai_builder_deployment", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)


def test_staging_transport_predicates_reject_local_or_plaintext_endpoints() -> None:
    assert preflight._is_remote_tls("https://builder.staging.example", ("https://",))
    assert not preflight._is_remote_tls("http://builder.staging.example", ("https://",))
    assert not preflight._is_remote_tls("https://localhost:8090", ("https://",))
    assert preflight._postgres_tls(
        "postgresql+psycopg://user:masked@db.staging.example/zylora?sslmode=verify-full"
    )
    assert not preflight._postgres_tls("postgresql+psycopg://user:masked@db.staging.example/zylora")


@pytest.mark.asyncio
async def test_staging_preflight_reports_only_missing_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in preflight.AI_REQUIRED_NAMES:
        monkeypatch.delenv(name, raising=False)
    status, checks = await preflight.run("staging", allow_write_probe=False)
    assert status == "blocked"
    assert checks[0].name == "configuration"
    assert "DATABASE_URL" in checks[0].detail
    assert "AI_BUILDER_SANDBOX_TOKEN" in checks[0].detail
    assert "=" not in checks[0].detail


@pytest.mark.asyncio
async def test_preflight_distinguishes_disabled_and_enabled_canary_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in preflight.AI_REQUIRED_NAMES:
        monkeypatch.setenv(name, "configured")
    monkeypatch.setenv("AI_BUILDER_ENVIRONMENT", "staging")
    monkeypatch.setenv("AI_BUILDER_PROVIDER_URL", "https://provider.staging.example")
    monkeypatch.setenv("AI_BUILDER_PROVIDER_TOKEN", "provider-token-with-at-least-32-characters")
    monkeypatch.setenv("AI_BUILDER_PROVIDER_NAME", "approved-provider")
    monkeypatch.setenv("AI_BUILDER_SANDBOX_URL", "https://sandbox.staging.example")
    monkeypatch.setenv("AI_BUILDER_SANDBOX_TOKEN", "sandbox-token-with-at-least-32-characters")

    settings = SimpleNamespace(
        environment="staging",
        ai_builder_enabled=False,
        ai_builder_rollout_mode="canary",
        ai_builder_canary_users=frozenset(),
        database_url=(
            "postgresql+psycopg://user:masked@db.staging.example/zylora?sslmode=verify-full"
        ),
        redis_url="rediss://cache.staging.example/0",
        celery_broker_url="rediss://broker.staging.example/1",
        celery_result_backend="rediss://broker.staging.example/2",
        ai_builder_url="https://builder.staging.example",
        ai_builder_preview_origin="https://preview.staging.example",
        ai_builder_service_token="builder-token-with-at-least-32-characters",
        cookie_secure=True,
        allowed_origins=("https://staging.example",),
        admin_origin="https://admin.staging.example",
        allowed_hosts=("staging.example", "admin.staging.example", "api.staging.example"),
        s3_endpoint_url="https://objects.staging.example",
    )

    async def dependency_check(*_args: object) -> preflight.Check:
        return preflight.Check("dependency", "pass", "reachable")

    monkeypatch.setattr(preflight, "Settings", lambda **_kwargs: settings)
    monkeypatch.setattr(preflight, "_database_check", dependency_check)
    monkeypatch.setattr(preflight, "_redis_check", dependency_check)
    monkeypatch.setattr(preflight, "_builder_check", dependency_check)
    monkeypatch.setattr(
        preflight,
        "_storage_check",
        lambda *_args: preflight.Check("artifact_storage", "pass", "verified"),
    )

    status, checks = await preflight.run("staging", allow_write_probe=False)
    assert status == "ready_for_staging_validation"
    assert next(check for check in checks if check.name == "feature_flag").status == "pass"
    assert next(check for check in checks if check.name == "canary_scope").status == "pass"

    settings.ai_builder_enabled = True
    settings.ai_builder_canary_users = frozenset({"11111111-1111-4111-8111-111111111111"})
    status, checks = await preflight.run(
        "staging", allow_write_probe=False, activation_state="canary"
    )
    assert status == "ready_for_staging_validation"
    assert next(check for check in checks if check.name == "feature_flag").status == "pass"
    assert next(check for check in checks if check.name == "canary_scope").status == "pass"
