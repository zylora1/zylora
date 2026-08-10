import pytest
from pydantic import ValidationError
from zylora_api.core.config import Settings


def production_settings(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "_env_file": None,
        "environment": "production",
        "database_url": "postgresql+psycopg://zylora:secret@db.example.com/zylora",
        "redis_url": "rediss://cache.example.com/0",
        "web_origins": "https://app.example.com",
        "admin_origin": "https://admin.example.com",
        "trusted_hosts": "app.example.com,admin.example.com,api.example.com",
        "auth_secret": "production-auth-secret-with-at-least-32-characters",
        "cookie_secure": True,
        "google_client_id": "google-client",
        "google_client_secret": "google-secret",
        "google_redirect_uri": "https://app.example.com/api/v1/auth/google/callback",
        "smtp_host": "smtp.example.com",
        "contact_recipient_email": "support@example.com",
        "storage_provider": "s3",
        "s3_bucket": "zylora-production",
        "s3_access_key": "production-access-key",
        "s3_secret_key": "production-secret-key",
        "turnstile_enabled": True,
        "turnstile_site_key": "production-site-key",
        "turnstile_secret_key": "production-turnstile-secret",
        "turnstile_allowed_hostnames": "app.example.com,admin.example.com",
        "ai_provider": "openai",
        "openai_api_key": "production-openai-secret",
        "domain_provider": "cloudflare",
        "cloudflare_api_token": "production-cloudflare-token",
        "cloudflare_zone_id": "zone-id",
        "cloudflare_published_origin": "origin.example.com",
        "published_site_base_domain": "sites.example.com",
    }
    values.update(overrides)
    return values


def test_production_requires_turnstile() -> None:
    with pytest.raises(ValidationError, match="Turnstile verification must be configured"):
        Settings(**production_settings(turnstile_enabled=False))


def test_production_rejects_cloudflare_test_keys() -> None:
    with pytest.raises(ValidationError, match="cannot use Cloudflare test values"):
        Settings(
            **production_settings(
                turnstile_site_key="1x00000000000000000000AA",
                turnstile_secret_key="1x0000000000000000000000000000000AA",
            )
        )


def test_production_requires_exact_user_and_admin_hostnames() -> None:
    with pytest.raises(ValidationError, match="hostnames must exactly match"):
        Settings(**production_settings(turnstile_allowed_hostnames="app.example.com"))


def test_production_accepts_provider_keys_and_exact_hostnames() -> None:
    settings = Settings(**production_settings())
    assert settings.turnstile_enabled is True
    assert settings.turnstile_allowed_hostname_values == (
        "app.example.com",
        "admin.example.com",
    )


def test_production_requires_server_side_ai_provider_key() -> None:
    with pytest.raises(ValidationError, match="requires the OpenAI provider and API key"):
        Settings(**production_settings(ai_provider="disabled", openai_api_key=""))


def test_production_rejects_non_official_openai_base_url() -> None:
    with pytest.raises(ValidationError, match="official HTTPS API"):
        Settings(**production_settings(openai_base_url="https://proxy.example.com/v1"))


def test_production_requires_a_contact_delivery_recipient() -> None:
    with pytest.raises(ValidationError, match="contact delivery recipient"):
        Settings(**production_settings(contact_recipient_email=""))
