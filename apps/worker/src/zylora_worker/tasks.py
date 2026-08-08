from __future__ import annotations

from typing import TypedDict

from zylora_worker import __version__
from zylora_worker.celery_app import celery_app


class WorkerHealthResult(TypedDict):
    service: str
    status: str
    version: str
    request_id: str


@celery_app.task(name="zylora.operations.health", acks_late=True)  # type: ignore[untyped-decorator]
def worker_health(request_id: str) -> WorkerHealthResult:
    """Operational task used to verify real broker-to-worker execution."""

    if not request_id or len(request_id) > 128:
        raise ValueError("request_id must contain between 1 and 128 characters")
    return {
        "service": "zylora-worker",
        "status": "alive",
        "version": __version__,
        "request_id": request_id,
    }
