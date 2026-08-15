from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).parents[4] / "scripts" / "check_chatbot_whatsapp_deployment.py"
SPEC = importlib.util.spec_from_file_location("check_chatbot_whatsapp_deployment", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)


def configured_settings() -> SimpleNamespace:
    return SimpleNamespace(
        environment="staging",
        knowledge_ingestion_enabled=True,
        whatsapp_enabled=True,
        storage_provider="s3",
        ai_provider="openai",
        openai_api_key="must-never-appear-in-report",
        document_scanner_provider="clamav",
        twilio_account_sid="ACmust-never-appear",
        twilio_auth_token="must-never-appear-in-report",
        twilio_whatsapp_from="+10000000000",
        twilio_messaging_service_sid=None,
        twilio_lead_template_content_sid="HXlead",
        twilio_test_template_content_sid="HXtest",
        twilio_status_callback_base_url="https://api.staging.example",
    )


def test_chatbot_whatsapp_preflight_checks_routes_workers_and_redacts_secrets() -> None:
    report = preflight.evaluate(
        configured_settings(),
        target="staging",
        require_knowledge=True,
        require_whatsapp=True,
    )
    assert report["ready"] is True
    assert all(report["checks"].values())
    serialized = json.dumps(report)
    assert "must-never-appear" not in serialized
    assert "ACmust-never-appear" not in serialized


def test_chatbot_whatsapp_preflight_fails_closed_for_disabled_activation() -> None:
    settings = configured_settings()
    settings.whatsapp_enabled = False
    report = preflight.evaluate(
        settings,
        target="staging",
        require_knowledge=True,
        require_whatsapp=True,
    )
    assert report["ready"] is False
    assert report["checks"]["whatsapp_feature_required_state"] is False
