from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from zylora_api.core.correlation import correlation_id_context


class JsonFormatter(logging.Formatter):
    """Small structured formatter with a fixed safe field set."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None)
            or correlation_id_context.get(),
        }
        for field in (
            "job_id",
            "project_id",
            "generation_id",
            "worker_id",
            "attempt",
            "state_transition",
            "website_id",
            "source_id",
            "index_id",
            "notification_id",
            "event_type",
            "provider_message_sid",
            "duration_ms",
            "provider",
            "model",
            "artifact_bytes",
            "outcome",
            "safe_error_code",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
