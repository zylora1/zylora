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

    @model_validator(mode="after")
    def validate_production_transport(self) -> Self:
        if self.environment == "production" and "localhost" in (
            self.celery_broker_url + self.celery_result_backend
        ):
            raise ValueError("production worker transport cannot use localhost")
        if not 1 <= self.worker_concurrency <= 64:
            raise ValueError("worker concurrency must be between 1 and 64")
        return self


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
