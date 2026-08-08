import json
import logging
import sys

from zylora_api.core.correlation import correlation_id_context
from zylora_api.core.logging import JsonFormatter, configure_logging


def test_json_formatter_includes_safe_correlation_and_exception_type() -> None:
    token = correlation_id_context.set("request-12345678")
    try:
        try:
            raise ValueError("sensitive detail")
        except ValueError:
            record = logging.LogRecord(
                "zylora.test",
                logging.ERROR,
                __file__,
                12,
                "operation failed",
                (),
                sys.exc_info(),
            )
        payload = json.loads(JsonFormatter().format(record))
    finally:
        correlation_id_context.reset(token)

    assert payload["message"] == "operation failed"
    assert payload["correlation_id"] == "request-12345678"
    assert payload["exception_type"] == "ValueError"
    assert "sensitive detail" not in payload


def test_configure_logging_replaces_root_handlers() -> None:
    configure_logging("warning")
    root = logging.getLogger()
    assert root.level == logging.WARNING
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
