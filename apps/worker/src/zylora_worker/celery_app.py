from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]

from zylora_worker import __version__
from zylora_worker.config import WorkerSettings, get_worker_settings


def create_celery(settings: WorkerSettings | None = None) -> Celery:
    resolved = settings or get_worker_settings()
    application = Celery(
        "zylora-worker",
        broker=resolved.celery_broker_url,
        backend=resolved.celery_result_backend,
        include=["zylora_worker.tasks"],
    )
    application.conf.update(
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        enable_utc=True,
        timezone="UTC",
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=270,
        task_time_limit=300,
        broker_connection_retry_on_startup=True,
        result_expires=3600,
        beat_schedule={
            "zylora-publishing-outbox": {
                "task": "zylora.publishing.dispatch_outbox",
                "schedule": 10.0,
            }
        },
    )
    application.conf.zylora_version = __version__
    return application


celery_app = create_celery()
