from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]
StorageProvider = Literal["s3", "memory", "disabled"]
AiProvider = Literal["openai", "disabled"]


class Settings(BaseSettings):
    """Typed runtime configuration with production safety validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Environment = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://zylora:zylora_dev_only@localhost:5432/zylora"
    redis_url: str = "redis://localhost:6379/0"
    web_origins: str = "http://localhost:3000"
    admin_origin: str = "http://admin.localhost:3000"
    trusted_hosts: str = "localhost,127.0.0.1,testserver,admin.localhost"
    trusted_proxy_ips: str = ""
    cloudflare_country_header_trusted: bool = False

    auth_secret: str = "zylora_development_auth_secret_change_me"  # noqa: S105
    cookie_secure: bool = False
    user_session_minutes: int = 60 * 24 * 30
    admin_session_minutes: int = 30
    verification_minutes: int = 15
    password_reset_minutes: int = 15
    turnstile_enabled: bool = False
    turnstile_site_key: str | None = None
    turnstile_secret_key: str | None = None
    turnstile_allowed_hostnames: str = "localhost,admin.localhost,testserver"
    turnstile_timeout_seconds: float = 5.0
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_start_tls: bool = True
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@zylora.local"

    storage_provider: StorageProvider = "disabled"
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_force_path_style: bool = True

    ai_provider: AiProvider = "disabled"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.6-terra"
    ai_timeout_seconds: float = 45.0
    ai_max_output_tokens: int = 4000

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        return tuple(value.strip() for value in self.web_origins.split(",") if value.strip())

    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        return tuple(value.strip() for value in self.trusted_hosts.split(",") if value.strip())

    @property
    def trusted_proxy_addresses(self) -> tuple[str, ...]:
        return tuple(value.strip() for value in self.trusted_proxy_ips.split(",") if value.strip())

    @property
    def turnstile_allowed_hostname_values(self) -> tuple[str, ...]:
        return tuple(
            value.strip().casefold()
            for value in self.turnstile_allowed_hostnames.split(",")
            if value.strip()
        )

    @model_validator(mode="after")
    def validate_environment_safety(self) -> Self:
        if not 1 <= self.turnstile_timeout_seconds <= 10:
            raise ValueError("Turnstile timeout must be between 1 and 10 seconds")

        if not 5 <= self.ai_timeout_seconds <= 120:
            raise ValueError("AI timeout must be between 5 and 120 seconds")
        if not 500 <= self.ai_max_output_tokens <= 8000:
            raise ValueError("AI max output tokens must be between 500 and 8000")

        if self.storage_provider == "memory" and self.environment != "test":
            raise ValueError("memory object storage is permitted only in the test environment")

        if self.storage_provider == "s3":
            required = {
                "s3_bucket": self.s3_bucket,
                "s3_access_key": self.s3_access_key,
                "s3_secret_key": self.s3_secret_key,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError(f"missing required S3 configuration: {', '.join(missing)}")

        if self.environment == "production":
            if self.storage_provider == "disabled":
                raise ValueError("production object storage must be configured")
            unsafe_fragments = ("localhost", "zylora_dev_only", "testserver")
            production_values = (
                self.database_url,
                self.redis_url,
                self.web_origins,
                self.admin_origin,
                self.trusted_hosts,
                self.auth_secret,
                self.google_redirect_uri,
                self.s3_access_key or "",
                self.s3_secret_key or "",
            )
            if any(
                fragment in value for value in production_values for fragment in unsafe_fragments
            ):
                raise ValueError("production configuration contains development-only values")
            if not self.allowed_origins or not all(
                origin.startswith("https://") for origin in self.allowed_origins
            ):
                raise ValueError("production web origins must be explicit HTTPS origins")
            if not self.admin_origin.startswith("https://"):
                raise ValueError("production admin origin must be an explicit HTTPS origin")
            if len(self.auth_secret) < 32:
                raise ValueError("production auth secret must contain at least 32 characters")
            if not self.cookie_secure:
                raise ValueError("production authentication cookies must be secure")
            if not self.google_client_id or not self.google_client_secret:
                raise ValueError("production Google OAuth credentials must be configured")
            allowed_callbacks = {
                f"{origin.rstrip('/')}/api/v1/auth/google/callback"
                for origin in self.allowed_origins
            }
            if self.google_redirect_uri not in allowed_callbacks:
                raise ValueError("production Google redirect URI must use an exact User Web origin")
            if not self.smtp_host:
                raise ValueError("production SMTP delivery must be configured")
            if (
                not self.turnstile_enabled
                or not self.turnstile_site_key
                or not self.turnstile_secret_key
            ):
                raise ValueError("production Turnstile verification must be configured")
            if self.ai_provider != "openai" or not self.openai_api_key:
                raise ValueError("production AI editing requires the OpenAI provider and API key")
            if self.openai_base_url != "https://api.openai.com/v1":
                raise ValueError("production OpenAI base URL must use the official HTTPS API")
            test_site_keys = {
                "1x00000000000000000000AA",
                "2x00000000000000000000AB",
                "1x00000000000000000000BB",
                "2x00000000000000000000BB",
                "3x00000000000000000000FF",
            }
            test_secret_keys = {
                "1x0000000000000000000000000000000AA",
                "2x0000000000000000000000000000000AA",
                "3x0000000000000000000000000000000AA",
            }
            if (
                self.turnstile_site_key in test_site_keys
                or self.turnstile_secret_key in test_secret_keys
            ):
                raise ValueError("production Turnstile keys cannot use Cloudflare test values")
            expected_turnstile_hosts = {
                hostname
                for origin in (*self.allowed_origins, self.admin_origin)
                if (hostname := urlparse(origin).hostname) is not None
            }
            if set(self.turnstile_allowed_hostname_values) != expected_turnstile_hosts:
                raise ValueError(
                    "production Turnstile hostnames must exactly match User and Admin origins"
                )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
