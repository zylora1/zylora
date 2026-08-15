from __future__ import annotations

import argparse
import json
from typing import Any

from pydantic import ValidationError
from zylora_api.app import create_app
from zylora_api.core.config import Settings
from zylora_worker.celery_app import celery_app

CALLBACK_ROUTE = "/api/v1/webhooks/twilio/whatsapp/status"
KNOWLEDGE_ROUTE = "/api/v1/websites/{website_id}/knowledge"
CHATBOT_TASK = "zylora.chatbot.dispatch_outbox"
LEAD_CHANNEL_TASK = "zylora.notifications.dispatch_lead_channels"


def _safe_validation_errors(error: ValidationError) -> list[dict[str, str]]:
    return [
        {
            "field": ".".join(str(part) for part in item["loc"]),
            "message": str(item["msg"]),
        }
        for item in error.errors(include_url=False, include_context=False, include_input=False)
    ]


def evaluate(
    settings: Settings,
    *,
    target: str,
    require_knowledge: bool,
    require_whatsapp: bool,
) -> dict[str, Any]:
    routes = set(create_app().openapi()["paths"])
    schedule = celery_app.conf.beat_schedule or {}
    scheduled_tasks = {str(item.get("task")) for item in schedule.values()}
    checks = {
        "environment_matches_target": settings.environment == target,
        "knowledge_route_registered": KNOWLEDGE_ROUTE in routes,
        "twilio_callback_route_registered": CALLBACK_ROUTE in routes,
        "chatbot_worker_dispatch_registered": CHATBOT_TASK in scheduled_tasks,
        "lead_channel_dispatch_registered": LEAD_CHANNEL_TASK in scheduled_tasks,
        "knowledge_feature_required_state": (
            settings.knowledge_ingestion_enabled if require_knowledge else True
        ),
        "whatsapp_feature_required_state": (
            settings.whatsapp_enabled if require_whatsapp else True
        ),
    }
    if settings.knowledge_ingestion_enabled:
        checks.update(
            {
                "knowledge_uses_durable_storage": settings.storage_provider == "s3",
                "knowledge_embedding_provider_configured": (
                    settings.ai_provider == "openai" and bool(settings.openai_api_key)
                ),
                "knowledge_scanner_configured": (settings.document_scanner_provider == "clamav"),
            }
        )
    if settings.whatsapp_enabled:
        checks.update(
            {
                "twilio_account_configured": bool(settings.twilio_account_sid),
                "twilio_auth_configured": bool(settings.twilio_auth_token),
                "twilio_sender_configured": bool(
                    settings.twilio_whatsapp_from or settings.twilio_messaging_service_sid
                ),
                "twilio_templates_configured": bool(
                    settings.twilio_lead_template_content_sid
                    and settings.twilio_test_template_content_sid
                ),
                "twilio_callback_is_https": bool(
                    settings.twilio_status_callback_base_url
                    and settings.twilio_status_callback_base_url.startswith("https://")
                ),
            }
        )
    return {
        "target": target,
        "environment": settings.environment,
        "features": {
            "knowledge_ingestion_enabled": settings.knowledge_ingestion_enabled,
            "whatsapp_enabled": settings.whatsapp_enabled,
        },
        "checks": checks,
        "ready": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Secret-safe Chatbot Knowledge and Twilio deployment preflight."
    )
    parser.add_argument("--target", choices=("staging", "production"), required=True)
    parser.add_argument("--require-knowledge", action="store_true")
    parser.add_argument("--require-whatsapp", action="store_true")
    args = parser.parse_args()
    try:
        settings = Settings()
    except ValidationError as error:
        print(json.dumps({"ready": False, "errors": _safe_validation_errors(error)}))
        raise SystemExit(1) from None
    report = evaluate(
        settings,
        target=args.target,
        require_knowledge=args.require_knowledge,
        require_whatsapp=args.require_whatsapp,
    )
    print(json.dumps(report, sort_keys=True))
    if not report["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
