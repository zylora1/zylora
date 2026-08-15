from uuid import UUID

import pytest
from pydantic import ValidationError
from zylora_api.core.config import Settings


def test_development_defaults_are_explicit_and_safe_for_local_services() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.storage_provider == "disabled"
    assert settings.allowed_hosts == ("localhost", "127.0.0.1", "testserver", "admin.localhost")


def test_memory_storage_is_test_only() -> None:
    with pytest.raises(ValidationError, match="permitted only in the test environment"):
        Settings(_env_file=None, environment="development", storage_provider="memory")


def test_resend_provider_requires_an_api_key() -> None:
    with pytest.raises(ValidationError, match="Resend email delivery requires an API key"):
        Settings(_env_file=None, email_provider="resend")

    settings = Settings(
        _env_file=None,
        email_provider="resend",
        resend_api_key="resend-test-key",
    )
    assert settings.email_provider == "resend"


def test_production_rejects_development_credentials() -> None:
    with pytest.raises(ValidationError, match="production object storage must be configured"):
        Settings(_env_file=None, environment="production")


def test_production_rejects_local_service_endpoints() -> None:
    with pytest.raises(ValidationError, match="development-only values"):
        Settings(
            _env_file=None,
            environment="production",
            storage_provider="s3",
            s3_endpoint_url="https://objects.example.com",
            s3_bucket="zylora-production",
            s3_access_key="production-access-key",
            s3_secret_key="production-secret-key",
        )


def test_production_google_callback_must_use_an_exact_user_origin() -> None:
    with pytest.raises(ValidationError, match="exact User Web origin"):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+psycopg://zylora:secret@db.example.com/zylora?sslmode=require",
            redis_url="rediss://cache.example.com/0",
            celery_broker_url="rediss://broker.example.com/1",
            celery_result_backend="rediss://broker.example.com/2",
            web_origins="https://app.example.com",
            admin_origin="https://admin.example.com",
            trusted_hosts="app.example.com,admin.example.com,api.example.com",
            auth_secret="production-auth-secret-with-at-least-32-characters",
            cookie_secure=True,
            google_client_id="google-client",
            google_client_secret="google-secret",
            google_redirect_uri="https://evil.example.com/api/v1/auth/google/callback",
            smtp_host="smtp.example.com",
            storage_provider="s3",
            s3_bucket="zylora-production",
            s3_access_key="production-access-key",
            s3_secret_key="production-secret-key",
        )


def test_enabled_ai_builder_requires_durable_dependencies() -> None:
    with pytest.raises(ValidationError, match="durable S3-compatible storage"):
        Settings(
            _env_file=None,
            environment="development",
            ai_builder_enabled=True,
            ai_builder_service_token="builder-service-token-with-32-characters",
        )
    with pytest.raises(ValidationError, match="32-character service token"):
        Settings(
            _env_file=None,
            environment="development",
            storage_provider="s3",
            s3_bucket="development-artifacts",
            s3_access_key="development-access",
            s3_secret_key="development-secret",
            ai_builder_enabled=True,
        )


def test_ai_builder_limits_are_bounded() -> None:
    with pytest.raises(ValidationError, match="active AI job limit"):
        Settings(_env_file=None, max_active_ai_jobs_per_user=0)
    with pytest.raises(ValidationError, match="AI generation retries"):
        Settings(_env_file=None, ai_max_retries=9)
    with pytest.raises(ValidationError, match="AI artifact limit"):
        Settings(_env_file=None, ai_max_artifact_bytes=1)


def test_database_and_artifact_delivery_limits_are_bounded() -> None:
    with pytest.raises(ValidationError, match="database pool size"):
        Settings(_env_file=None, database_pool_size=0)
    with pytest.raises(ValidationError, match="lock timeout must be shorter"):
        Settings(
            _env_file=None,
            database_statement_timeout_ms=5000,
            database_lock_timeout_ms=5000,
        )
    with pytest.raises(ValidationError, match="artifact URL lifetime"):
        Settings(_env_file=None, ai_artifact_url_ttl_seconds=59)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("database_max_overflow", 201, "database max overflow"),
        ("database_pool_timeout_seconds", 0, "database pool timeout"),
        ("database_pool_recycle_seconds", 59, "database pool recycle"),
        ("database_statement_timeout_ms", 999, "database statement timeout"),
        ("database_lock_timeout_ms", 99, "database lock timeout"),
        ("ai_artifact_url_ttl_seconds", 901, "artifact URL lifetime"),
    ],
)
def test_database_transport_bounds_fail_closed(field: str, value: int, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **{field: value})


def test_ai_builder_canary_ids_are_typed_and_fail_closed() -> None:
    user_id = UUID("11111111-1111-4111-8111-111111111111")
    settings = Settings(_env_file=None, ai_builder_canary_user_ids=str(user_id))
    assert settings.ai_builder_canary_users == frozenset({user_id})
    with pytest.raises(ValidationError, match="canary User IDs"):
        Settings(_env_file=None, ai_builder_canary_user_ids="not-a-uuid")


def test_staging_ai_builder_rejects_local_dependencies() -> None:
    with pytest.raises(ValidationError, match="dependencies must be remote"):
        Settings(
            _env_file=None,
            environment="staging",
            auth_secret="staging-auth-secret-long-enough-for-validation",
            storage_provider="s3",
            s3_bucket="staging-artifacts",
            s3_access_key="staging-access",
            s3_secret_key="staging-secret",
            ai_builder_enabled=True,
            ai_builder_service_token="staging-service-token-long-enough-for-validation",
            ai_builder_canary_user_ids="11111111-1111-4111-8111-111111111111",
        )


def test_staging_ai_builder_accepts_only_remote_secure_dependencies() -> None:
    user_id = "11111111-1111-4111-8111-111111111111"
    settings = Settings(
        _env_file=None,
        environment="staging",
        database_url=(
            "postgresql+psycopg://zylora:masked@db.staging.example/zylora?sslmode=verify-full"
        ),
        redis_url="rediss://cache.staging.example/0",
        celery_broker_url="rediss://broker.staging.example/1",
        celery_result_backend="rediss://broker.staging.example/2",
        web_origins="https://staging.example.com",
        admin_origin="https://admin.staging.example.com",
        trusted_hosts="staging.example.com,admin.staging.example.com,api.staging.example.com",
        auth_secret="staging-auth-secret-long-enough-for-validation",
        cookie_secure=True,
        storage_provider="s3",
        s3_endpoint_url="https://objects.staging.example",
        s3_bucket="staging-artifacts",
        s3_access_key="staging-access",
        s3_secret_key="staging-secret",
        ai_builder_enabled=True,
        ai_builder_service_token="staging-service-token-long-enough-for-validation",
        ai_builder_canary_user_ids=user_id,
        ai_builder_url="https://builder.staging.example",
        ai_builder_preview_origin="https://preview.staging.example",
    )
    assert settings.ai_builder_enabled is True
    assert settings.ai_builder_canary_users == frozenset({UUID(user_id)})


def test_staging_ai_builder_rejects_development_auth_secret() -> None:
    with pytest.raises(ValidationError, match="non-development auth secret"):
        Settings(
            _env_file=None,
            environment="staging",
            database_url=(
                "postgresql+psycopg://zylora:masked@db.staging.example/zylora?sslmode=verify-full"
            ),
            redis_url="rediss://cache.staging.example/0",
            celery_broker_url="rediss://broker.staging.example/1",
            celery_result_backend="rediss://broker.staging.example/2",
            web_origins="https://staging.example.com",
            admin_origin="https://admin.staging.example.com",
            trusted_hosts="staging.example.com,admin.staging.example.com,api.staging.example.com",
            cookie_secure=True,
            storage_provider="s3",
            s3_endpoint_url="https://objects.staging.example",
            s3_bucket="staging-artifacts",
            s3_access_key="staging-access",
            s3_secret_key="staging-secret",
            ai_builder_enabled=True,
            ai_builder_service_token="staging-service-token-long-enough-for-validation",
            ai_builder_canary_user_ids="11111111-1111-4111-8111-111111111111",
            ai_builder_url="https://builder.staging.example",
            ai_builder_preview_origin="https://preview.staging.example",
        )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        (
            {"database_url": "postgresql+psycopg://zylora:masked@db.staging.example/zylora"},
            "PostgreSQL must require TLS",
        ),
        ({"redis_url": "redis://cache.staging.example/0"}, "Redis must require TLS"),
        ({"ai_builder_url": "http://builder.staging.example"}, "URL must use HTTPS"),
        ({"s3_endpoint_url": "http://objects.staging.example"}, "storage must use HTTPS"),
        ({"cookie_secure": False}, "secure explicit origins"),
    ],
)
def test_staging_ai_builder_transport_layers_fail_closed(
    override: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "environment": "staging",
        "database_url": (
            "postgresql+psycopg://zylora:masked@db.staging.example/zylora?sslmode=verify-full"
        ),
        "redis_url": "rediss://cache.staging.example/0",
        "celery_broker_url": "rediss://broker.staging.example/1",
        "celery_result_backend": "rediss://broker.staging.example/2",
        "web_origins": "https://staging.example.com",
        "admin_origin": "https://admin.staging.example.com",
        "trusted_hosts": "staging.example.com,admin.staging.example.com,api.staging.example.com",
        "auth_secret": "staging-auth-secret-long-enough-for-validation",
        "cookie_secure": True,
        "storage_provider": "s3",
        "s3_endpoint_url": "https://objects.staging.example",
        "s3_bucket": "staging-artifacts",
        "s3_access_key": "staging-access",
        "s3_secret_key": "staging-secret",
        "ai_builder_enabled": True,
        "ai_builder_service_token": "staging-service-token-long-enough-for-validation",
        "ai_builder_canary_user_ids": "11111111-1111-4111-8111-111111111111",
        "ai_builder_url": "https://builder.staging.example",
        "ai_builder_preview_origin": "https://preview.staging.example",
    }
    values.update(override)
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **values)


def test_staging_ai_builder_preview_origin_is_dedicated() -> None:
    values: dict[str, object] = {
        "environment": "staging",
        "database_url": (
            "postgresql+psycopg://zylora:masked@db.staging.example/zylora?sslmode=verify-full"
        ),
        "redis_url": "rediss://cache.staging.example/0",
        "celery_broker_url": "rediss://broker.staging.example/1",
        "celery_result_backend": "rediss://broker.staging.example/2",
        "web_origins": "https://staging.example.com",
        "admin_origin": "https://admin.staging.example.com",
        "trusted_hosts": "staging.example.com,admin.staging.example.com,api.staging.example.com",
        "auth_secret": "staging-auth-secret-long-enough-for-validation",
        "cookie_secure": True,
        "storage_provider": "s3",
        "s3_endpoint_url": "https://objects.staging.example",
        "s3_bucket": "staging-artifacts",
        "s3_access_key": "staging-access",
        "s3_secret_key": "staging-secret",
        "ai_builder_enabled": True,
        "ai_builder_service_token": "staging-service-token-long-enough-for-validation",
        "ai_builder_canary_user_ids": "11111111-1111-4111-8111-111111111111",
        "ai_builder_url": "https://builder.staging.example",
    }
    with pytest.raises(ValidationError, match="preview origin must use remote HTTPS"):
        Settings(_env_file=None, **values)
    values["ai_builder_preview_origin"] = "https://staging.example.com"
    with pytest.raises(ValidationError, match="preview origin must be dedicated"):
        Settings(_env_file=None, **values)
