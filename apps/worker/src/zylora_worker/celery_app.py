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
        worker_prefetch_multiplier=resolved.celery_prefetch_multiplier,
        task_soft_time_limit=resolved.celery_soft_time_limit_seconds,
        task_time_limit=resolved.celery_time_limit_seconds,
        broker_connection_retry_on_startup=True,
        result_expires=3600,
        worker_concurrency=resolved.worker_concurrency,
        worker_max_tasks_per_child=resolved.celery_max_tasks_per_child,
        broker_transport_options={
            "visibility_timeout": resolved.celery_visibility_timeout_seconds,
        },
        result_backend_transport_options={
            "visibility_timeout": resolved.celery_visibility_timeout_seconds,
        },
        task_annotations={
            "zylora.ai_builder.execute_generation": {
                "soft_time_limit": resolved.ai_generation_soft_time_limit_seconds,
                "time_limit": resolved.ai_generation_time_limit_seconds,
            }
        },
        beat_schedule={
            "zylora-publishing-outbox": {
                "task": "zylora.publishing.dispatch_outbox",
                "schedule": 10.0,
            },
            "zylora-ai-builder-outbox": {
                "task": "zylora.ai_builder.dispatch_outbox",
                "schedule": 10.0,
            },
            "zylora-ai-builder-recovery": {
                "task": "zylora.ai_builder.recover_stale",
                "schedule": 30.0,
            },
            "zylora-export-outbox": {
                "task": "zylora.exports.dispatch_outbox",
                "schedule": 10.0,
            },
            "zylora-chatbot-outbox": {
                "task": "zylora.chatbot.dispatch_outbox",
                "schedule": 10.0,
            },
            "zylora-transactional-email-outbox": {
                "task": "zylora.notifications.dispatch_transactional_email",
                "schedule": 10.0,
            },
            "zylora-lead-channel-outbox": {
                "task": "zylora.notifications.dispatch_lead_channels",
                "schedule": 10.0,
            },
            "zylora-campaign-outbox": {
                "task": "zylora.campaigns.dispatch_deliveries",
                "schedule": 10.0,
            },
            "zylora-campaign-schedules": {
                "task": "zylora.campaigns.start_scheduled",
                "schedule": 30.0,
            },
            "zylora-blog-schedules": {
                "task": "zylora.blog.publish_scheduled",
                "schedule": 30.0,
            },
            "zylora-analytics-rollups": {
                "task": "zylora.analytics.refresh",
                "schedule": 60.0,
            },
            "zylora-activation-maintenance": {
                "task": "zylora.analytics.activation_maintenance",
                "schedule": 3600.0,
            },
        },
    )
    application.conf.zylora_version = __version__
    return application


celery_app = create_celery()
