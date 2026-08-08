from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]
StorageProvider = Literal["s3", "memory", "disabled"]


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
    trusted_hosts: str = "localhost,127.0.0.1,testserver"

    storage_provider: StorageProvider = "disabled"
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_force_path_style: bool = True

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        return tuple(value.strip() for value in self.web_origins.split(",") if value.strip())

    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        return tuple(value.strip() for value in self.trusted_hosts.split(",") if value.strip())

    @model_validator(mode="after")
    def validate_environment_safety(self) -> Self:
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
                self.trusted_hosts,
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

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
