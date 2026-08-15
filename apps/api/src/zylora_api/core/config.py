from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]
StorageProvider = Literal["s3", "memory", "disabled"]
AiProvider = Literal["openai", "disabled"]
DomainProviderName = Literal["cloudflare", "disabled", "memory"]
DocumentScannerProvider = Literal["clamav", "test"]


CLOUDFLARE_TURNSTILE_TEST_SITE_KEYS = frozenset(
    {
        "1x00000000000000000000AA",
        "2x00000000000000000000AB",
        "1x00000000000000000000BB",
        "2x00000000000000000000BB",
        "3x00000000000000000000FF",
    }
)
CLOUDFLARE_TURNSTILE_TEST_SECRET_KEYS = frozenset(
    {
        "1x0000000000000000000000000000000AA",
        "2x0000000000000000000000000000000AA",
        "3x0000000000000000000000000000000AA",
    }
)


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
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 900
    database_statement_timeout_ms: int = 30_000
    database_lock_timeout_ms: int = 5_000
    redis_url: str = "redis://localhost:6379/0"
    web_origins: str = "http://localhost:3000"
    admin_origin: str = "http://admin.localhost:3000"
    trusted_hosts: str = "localhost,127.0.0.1,testserver,admin.localhost"
    trusted_proxy_ips: str = ""
    cloudflare_country_header_trusted: bool = False
    domain_provider: DomainProviderName = "disabled"
    cloudflare_api_token: str | None = None
    cloudflare_zone_id: str | None = None
    cloudflare_published_origin: str | None = None
    published_site_base_domain: str = "sites.zylora.local"
    cloudflare_api_timeout_seconds: float = 5.0

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
    contact_recipient_email: str | None = None

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
    ai_builder_enabled: bool = False
    ai_builder_rollout_mode: Literal["canary", "global"] = "canary"
    ai_builder_canary_user_ids: str = ""
    ai_builder_preview_origin: str = ""
    ai_builder_url: str = "http://127.0.0.1:8090"
    ai_builder_service_token: str | None = None
    ai_builder_connect_timeout_seconds: float = 5.0
    ai_generation_timeout_seconds: float = 420.0
    max_ai_prompt_bytes: int = 8192
    ai_builder_max_output_tokens: int = 32000
    max_active_ai_jobs_per_user: int = 2
    max_ai_generations_per_window: int = 10
    ai_generation_window_seconds: int = 3600
    ai_max_retries: int = 4
    ai_job_lease_seconds: int = 600
    ai_max_artifact_bytes: int = 52_428_800
    ai_artifact_url_ttl_seconds: int = 300
    chatbot_embedding_model: str = "text-embedding-3-small"
    chatbot_embedding_dimension: int = 1536
    chatbot_generation_model: str = "gpt-5.6-terra"
    chatbot_retrieval_limit: int = 4
    chatbot_relevance_threshold: float = 0.2
    chatbot_max_context_characters: int = 12_000
    chatbot_chunk_characters: int = 900
    knowledge_ingestion_enabled: bool = False
    knowledge_max_file_bytes: int = 15_728_640
    knowledge_max_documents_per_website: int = 25
    knowledge_max_extracted_characters: int = 500_000
    knowledge_max_pdf_pages: int = 300
    knowledge_max_docx_entries: int = 2_000
    knowledge_max_docx_uncompressed_bytes: int = 52_428_800
    document_scanner_provider: DocumentScannerProvider = "clamav"
    clamav_host: str = "127.0.0.1"
    clamav_port: int = 3310
    clamav_timeout_seconds: float = 20.0

    whatsapp_enabled: bool = False
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None
    twilio_messaging_service_sid: str | None = None
    twilio_lead_template_content_sid: str | None = None
    twilio_test_template_content_sid: str | None = None
    twilio_status_callback_base_url: str | None = None
    twilio_timeout_seconds: float = 10.0

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

    @property
    def uses_official_turnstile_test_secret(self) -> bool:
        return self.environment in {"development", "test"} and (
            self.turnstile_secret_key in CLOUDFLARE_TURNSTILE_TEST_SECRET_KEYS
        )

    @property
    def ai_builder_canary_users(self) -> frozenset[UUID]:
        return frozenset(
            UUID(value.strip())
            for value in self.ai_builder_canary_user_ids.split(",")
            if value.strip()
        )

    @model_validator(mode="after")
    def validate_environment_safety(self) -> Self:
        if not 1 <= self.turnstile_timeout_seconds <= 10:
            raise ValueError("Turnstile timeout must be between 1 and 10 seconds")
        if not 1 <= self.database_pool_size <= 100:
            raise ValueError("database pool size must be between 1 and 100")
        if not 0 <= self.database_max_overflow <= 200:
            raise ValueError("database max overflow must be between 0 and 200")
        if not 1 <= self.database_pool_timeout_seconds <= 120:
            raise ValueError("database pool timeout must be between 1 and 120 seconds")
        if not 60 <= self.database_pool_recycle_seconds <= 3600:
            raise ValueError("database pool recycle must be between 60 and 3600 seconds")
        if not 1_000 <= self.database_statement_timeout_ms <= 120_000:
            raise ValueError("database statement timeout must be between 1000 and 120000 ms")
        if not 100 <= self.database_lock_timeout_ms <= 30_000:
            raise ValueError("database lock timeout must be between 100 and 30000 ms")
        if self.database_lock_timeout_ms >= self.database_statement_timeout_ms:
            raise ValueError("database lock timeout must be shorter than statement timeout")
        if not 1 <= self.cloudflare_api_timeout_seconds <= 15:
            raise ValueError("Cloudflare API timeout must be between 1 and 15 seconds")

        if not 5 <= self.ai_timeout_seconds <= 120:
            raise ValueError("AI timeout must be between 5 and 120 seconds")
        if not 1 <= self.ai_builder_connect_timeout_seconds <= 15:
            raise ValueError("AI builder connect timeout must be between 1 and 15 seconds")
        if not 30 <= self.ai_generation_timeout_seconds <= 900:
            raise ValueError("AI generation timeout must be between 30 and 900 seconds")
        if not 1_000 <= self.ai_builder_max_output_tokens <= 128_000:
            raise ValueError("AI builder output token limit must be between 1000 and 128000")
        if not 1024 <= self.max_ai_prompt_bytes <= 65_536:
            raise ValueError("AI prompt byte limit must be between 1 KiB and 64 KiB")
        if not 1 <= self.max_active_ai_jobs_per_user <= 10:
            raise ValueError("active AI job limit must be between 1 and 10")
        if not 1 <= self.max_ai_generations_per_window <= 100:
            raise ValueError("AI generation window limit must be between 1 and 100")
        if not 60 <= self.ai_generation_window_seconds <= 86_400:
            raise ValueError("AI generation window must be between 60 and 86400 seconds")
        if not 1 <= self.ai_max_retries <= 8:
            raise ValueError("AI generation retries must be between 1 and 8")
        if not 60 <= self.ai_job_lease_seconds <= 1800:
            raise ValueError("AI generation lease must be between 60 and 1800 seconds")
        if not 1_048_576 <= self.ai_max_artifact_bytes <= 262_144_000:
            raise ValueError("AI artifact limit must be between 1 MiB and 250 MiB")
        if not 60 <= self.ai_artifact_url_ttl_seconds <= 900:
            raise ValueError("AI artifact URL lifetime must be between 60 and 900 seconds")
        if self.ai_builder_enabled:
            if self.environment != "test" and self.storage_provider != "s3":
                raise ValueError("enabled AI builder requires durable S3-compatible storage")
            if not self.ai_builder_service_token or len(self.ai_builder_service_token) < 32:
                raise ValueError("enabled AI builder requires a 32-character service token")
            if not self.celery_broker_url.startswith(("redis://", "rediss://")):
                raise ValueError("enabled AI builder requires the durable Redis/Celery broker")
        try:
            canary_users = self.ai_builder_canary_users
        except ValueError as error:
            raise ValueError("AI builder canary User IDs must be valid UUIDs") from error
        if (
            self.environment in {"staging", "production"}
            and self.ai_builder_enabled
            and self.ai_builder_rollout_mode == "canary"
            and not canary_users
        ):
            raise ValueError("enabled AI builder canary requires at least one User ID")
        if self.ai_builder_enabled and not self.ai_builder_url.startswith(("http://", "https://")):
            raise ValueError("AI builder URL must be an explicit HTTP(S) origin")

        if not 500 <= self.ai_max_output_tokens <= 8000:
            raise ValueError("AI max output tokens must be between 500 and 8000")
        if not self.chatbot_embedding_model.strip():
            raise ValueError("chatbot embedding model must be configured")
        if not 8 <= self.chatbot_embedding_dimension <= 4096:
            raise ValueError("chatbot embedding dimension must be between 8 and 4096")
        if not self.chatbot_generation_model.strip():
            raise ValueError("chatbot generation model must be configured")
        if not 1 <= self.chatbot_retrieval_limit <= 10:
            raise ValueError("chatbot retrieval limit must be between 1 and 10")
        if not 0 <= self.chatbot_relevance_threshold <= 1:
            raise ValueError("chatbot relevance threshold must be between 0 and 1")
        if not 1_000 <= self.chatbot_max_context_characters <= 50_000:
            raise ValueError("chatbot context limit must be between 1000 and 50000 characters")
        if not 300 <= self.chatbot_chunk_characters <= 2_000:
            raise ValueError("chatbot chunk size must be between 300 and 2000 characters")
        if not 1_024 <= self.knowledge_max_file_bytes <= 52_428_800:
            raise ValueError("knowledge file limit must be between 1 KiB and 50 MiB")
        if not 1 <= self.knowledge_max_documents_per_website <= 100:
            raise ValueError("knowledge document limit must be between 1 and 100")
        if not 10_000 <= self.knowledge_max_extracted_characters <= 2_000_000:
            raise ValueError("knowledge extraction limit must be between 10000 and 2000000")
        if not 1 <= self.knowledge_max_pdf_pages <= 1_000:
            raise ValueError("knowledge PDF page limit must be between 1 and 1000")
        if not 1 <= self.knowledge_max_docx_entries <= 10_000:
            raise ValueError("knowledge DOCX entry limit must be between 1 and 10000")
        if not 1_048_576 <= self.knowledge_max_docx_uncompressed_bytes <= 262_144_000:
            raise ValueError("knowledge DOCX expansion limit must be between 1 MiB and 250 MiB")
        if not 1 <= self.clamav_timeout_seconds <= 60:
            raise ValueError("ClamAV timeout must be between 1 and 60 seconds")
        if not 1 <= self.twilio_timeout_seconds <= 30:
            raise ValueError("Twilio timeout must be between 1 and 30 seconds")
        if self.document_scanner_provider == "test" and self.environment != "test":
            raise ValueError("test document scanner is permitted only in the test environment")
        if self.knowledge_ingestion_enabled:
            if self.environment != "test" and self.storage_provider != "s3":
                raise ValueError(
                    "enabled knowledge ingestion requires durable S3-compatible storage"
                )
            if self.ai_provider != "openai" or not self.openai_api_key:
                raise ValueError("enabled knowledge ingestion requires the embedding provider")
            if self.environment != "test" and self.document_scanner_provider != "clamav":
                raise ValueError("enabled knowledge ingestion requires malware scanning")
        if self.whatsapp_enabled:
            required_twilio = (
                self.twilio_account_sid,
                self.twilio_auth_token,
                self.twilio_lead_template_content_sid,
                self.twilio_test_template_content_sid,
                self.twilio_status_callback_base_url,
            )
            if not all(required_twilio):
                raise ValueError("enabled WhatsApp delivery has incomplete Twilio configuration")
            if not self.twilio_whatsapp_from and not self.twilio_messaging_service_sid:
                raise ValueError("enabled WhatsApp delivery requires a sender or Messaging Service")
            if self.environment in {"staging", "production"} and not (
                self.twilio_status_callback_base_url or ""
            ).startswith("https://"):
                raise ValueError("Twilio status callbacks must use HTTPS outside development")

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

        if self.environment in {"staging", "production"} and self.ai_builder_enabled:
            if (
                len(self.auth_secret) < 32
                or self.auth_secret == "zylora_development_auth_secret_change_me"  # noqa: S105
            ):
                raise ValueError(
                    "staging/production AI Builder requires a non-development auth secret"
                )
            protected_values = (
                self.database_url,
                self.redis_url,
                self.celery_broker_url,
                self.celery_result_backend,
                self.ai_builder_url,
                self.s3_endpoint_url or "",
            )
            if any(
                fragment in value.casefold()
                for value in protected_values
                for fragment in ("localhost", "127.0.0.1", "::1", "zylora_dev_only")
            ):
                raise ValueError("staging/production AI Builder dependencies must be remote")
            database_query = parse_qs(urlparse(self.database_url).query)
            sslmode = database_query.get("sslmode", [""])[0].casefold()
            ssl = database_query.get("ssl", [""])[0].casefold()
            if sslmode not in {"require", "verify-ca", "verify-full"} and ssl not in {
                "1",
                "true",
            }:
                raise ValueError("staging/production AI Builder PostgreSQL must require TLS")
            if not all(
                value.startswith("rediss://")
                for value in (self.redis_url, self.celery_broker_url, self.celery_result_backend)
            ):
                raise ValueError("staging/production AI Builder Redis must require TLS")
            if not self.ai_builder_url.startswith("https://"):
                raise ValueError("staging/production AI Builder URL must use HTTPS")
            if not self.ai_builder_preview_origin.startswith("https://") or any(
                marker in self.ai_builder_preview_origin.casefold()
                for marker in ("localhost", "127.0.0.1", "::1", ".local")
            ):
                raise ValueError(
                    "staging/production AI Builder preview origin must use remote HTTPS"
                )
            if self.ai_builder_preview_origin.rstrip("/") in {
                *(origin.rstrip("/") for origin in self.allowed_origins),
                self.admin_origin.rstrip("/"),
            }:
                raise ValueError("AI Builder preview origin must be dedicated")
            if self.s3_endpoint_url and not self.s3_endpoint_url.startswith("https://"):
                raise ValueError("staging/production AI Builder storage must use HTTPS")
            if (
                not self.cookie_secure
                or not self.allowed_origins
                or any(not origin.startswith("https://") for origin in self.allowed_origins)
                or not self.admin_origin.startswith("https://")
                or any(
                    host in {"*", "localhost", "127.0.0.1", "testserver"}
                    for host in self.allowed_hosts
                )
            ):
                raise ValueError("staging/production AI Builder requires secure explicit origins")
        if self.environment == "production":
            if self.storage_provider == "disabled":
                raise ValueError("production object storage must be configured")
            unsafe_fragments = ("localhost", "zylora_dev_only", "testserver")
            production_values = (
                self.database_url,
                self.redis_url,
                self.celery_broker_url,
                self.celery_result_backend,
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
            database_query = parse_qs(urlparse(self.database_url).query)
            sslmode = database_query.get("sslmode", [""])[0].casefold()
            ssl = database_query.get("ssl", [""])[0].casefold()
            if sslmode not in {"require", "verify-ca", "verify-full"} and ssl not in {
                "1",
                "true",
            }:
                raise ValueError("production PostgreSQL transport must require TLS")
            if not all(
                value.startswith("rediss://")
                for value in (self.redis_url, self.celery_broker_url, self.celery_result_backend)
            ):
                raise ValueError("production Redis and Celery transports must require TLS")
            if self.s3_endpoint_url and not self.s3_endpoint_url.startswith("https://"):
                raise ValueError("production S3-compatible endpoint must use HTTPS")
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
            if not self.contact_recipient_email:
                raise ValueError("production contact delivery recipient must be configured")
            if (
                not self.turnstile_enabled
                or not self.turnstile_site_key
                or not self.turnstile_secret_key
            ):
                raise ValueError("production Turnstile verification must be configured")
            if self.ai_provider != "openai" or not self.openai_api_key:
                raise ValueError("production AI editing requires the OpenAI provider and API key")
            if self.ai_builder_enabled:
                if self.storage_provider != "s3":
                    raise ValueError("production AI builder requires durable S3-compatible storage")
                if not self.celery_broker_url.startswith(("redis://", "rediss://")):
                    raise ValueError(
                        "production AI builder requires the durable Redis/Celery broker"
                    )
                if not self.ai_builder_url.startswith("https://"):
                    raise ValueError("production AI builder URL must use HTTPS")
                if not self.ai_builder_service_token or len(self.ai_builder_service_token) < 32:
                    raise ValueError(
                        "production AI builder service token must contain at least 32 characters"
                    )
            if self.openai_base_url != "https://api.openai.com/v1":
                raise ValueError("production OpenAI base URL must use the official HTTPS API")
            if (
                self.turnstile_site_key in CLOUDFLARE_TURNSTILE_TEST_SITE_KEYS
                or self.turnstile_secret_key in CLOUDFLARE_TURNSTILE_TEST_SECRET_KEYS
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

            if self.domain_provider != "cloudflare":
                raise ValueError("production Website domains require the Cloudflare provider")
            required_cloudflare = {
                "cloudflare_api_token": self.cloudflare_api_token,
                "cloudflare_zone_id": self.cloudflare_zone_id,
                "cloudflare_published_origin": self.cloudflare_published_origin,
            }
            missing_cloudflare = [name for name, value in required_cloudflare.items() if not value]
            if missing_cloudflare:
                raise ValueError("missing required Cloudflare domain configuration")
            if ".local" in self.published_site_base_domain or "localhost" in (
                self.cloudflare_published_origin or ""
            ):
                raise ValueError("production Cloudflare domain configuration contains local hosts")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
