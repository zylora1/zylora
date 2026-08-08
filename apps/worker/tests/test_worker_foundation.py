import pytest
from pydantic import ValidationError
from zylora_worker.celery_app import celery_app
from zylora_worker.config import WorkerSettings
from zylora_worker.tasks import worker_health


def test_worker_health_task_is_deterministic_in_eager_mode() -> None:
    celery_app.conf.task_always_eager = True
    result = worker_health.apply(args=("foundation-check",), throw=True)

    assert result.get() == {
        "service": "zylora-worker",
        "status": "alive",
        "version": "0.1.0",
        "request_id": "foundation-check",
    }


def test_worker_health_rejects_unbounded_request_id() -> None:
    with pytest.raises(ValueError, match="between 1 and 128"):
        worker_health("x" * 129)


def test_production_worker_rejects_local_transport() -> None:
    with pytest.raises(ValidationError, match="cannot use localhost"):
        WorkerSettings(_env_file=None, environment="production")
