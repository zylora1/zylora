from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    worker_concurrency: int = 2
    celery_visibility_timeout_seconds: int = 900
    celery_soft_time_limit_seconds: int = 270
    celery_time_limit_seconds: int = 300
    celery_prefetch_multiplier: int = 1
    celery_max_tasks_per_child: int = 50
    ai_generation_soft_time_limit_seconds: int = 570
    ai_generation_time_limit_seconds: int = 600

    @model_validator(mode="after")
    def validate_production_transport(self) -> Self:
        if self.environment in {"staging", "production"}:
            if "localhost" in self.celery_broker_url + self.celery_result_backend:
                raise ValueError("staging/production worker transport cannot use localhost")
            if not self.celery_broker_url.startswith("rediss://") or not (
                self.celery_result_backend.startswith("rediss://")
            ):
                raise ValueError("staging/production worker transport must require TLS")
        if not 1 <= self.worker_concurrency <= 64:
            raise ValueError("worker concurrency must be between 1 and 64")
        if not 300 <= self.celery_visibility_timeout_seconds <= 86_400:
            raise ValueError("Celery visibility timeout must be between 300 and 86400 seconds")
        if not 30 <= self.celery_soft_time_limit_seconds <= 3600:
            raise ValueError("Celery soft time limit must be between 30 and 3600 seconds")
        if not self.celery_soft_time_limit_seconds < self.celery_time_limit_seconds:
            raise ValueError("Celery soft time limit must be shorter than the hard time limit")
        if not 30 <= self.ai_generation_soft_time_limit_seconds <= 3600:
            raise ValueError("AI generation soft time limit must be between 30 and 3600 seconds")
        if not self.ai_generation_soft_time_limit_seconds < self.ai_generation_time_limit_seconds:
            raise ValueError(
                "AI generation soft time limit must be shorter than its hard time limit"
            )
        if self.celery_visibility_timeout_seconds <= max(
            self.celery_time_limit_seconds, self.ai_generation_time_limit_seconds
        ):
            raise ValueError("Celery visibility timeout must exceed the hard time limit")
        if not 1 <= self.celery_prefetch_multiplier <= 4:
            raise ValueError("Celery prefetch multiplier must be between 1 and 4")
        if not 1 <= self.celery_max_tasks_per_child <= 1000:
            raise ValueError("Celery max tasks per child must be between 1 and 1000")
        return self


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
