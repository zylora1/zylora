import pytest
from pydantic import ValidationError
from zylora_api.core.config import Settings


def test_development_defaults_are_explicit_and_safe_for_local_services() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.storage_provider == "disabled"
    assert settings.allowed_hosts == ("localhost", "127.0.0.1", "testserver")


def test_memory_storage_is_test_only() -> None:
    with pytest.raises(ValidationError, match="permitted only in the test environment"):
        Settings(_env_file=None, environment="development", storage_provider="memory")


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
