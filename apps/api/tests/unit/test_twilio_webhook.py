from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from twilio.request_validator import RequestValidator  # type: ignore[import-untyped]
from zylora_api.api import twilio_webhooks
from zylora_api.app import create_app
from zylora_api.db.session import get_session
from zylora_api.modules.auth.http import get_crypto
from zylora_api.modules.auth.security import AuthCrypto


class Database:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_twilio_status_webhook_rejects_invalid_signature_and_accepts_exact_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "twilio-webhook-test-token"
    callback_url = "https://api.example.test/api/v1/webhooks/twilio/whatsapp/status"
    payload = {"MessageSid": "SM1234567890", "MessageStatus": "delivered", "Extra": "ok"}
    signature = RequestValidator(token).compute_signature(callback_url, payload)
    settings = SimpleNamespace(
        whatsapp_enabled=True,
        twilio_auth_token=token,
        twilio_status_callback_base_url="https://api.example.test",
    )
    database = Database()
    applied: list[dict[str, object]] = []

    class Service:
        def __init__(self, *_args: object) -> None:
            pass

        async def apply_callback(self, **values: object) -> None:
            applied.append(values)

    app = create_app()
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_crypto] = lambda: AuthCrypto(
        "twilio-webhook-route-test-secret-long-enough"
    )
    app.dependency_overrides[twilio_webhooks.get_settings] = lambda: settings
    monkeypatch.setattr(twilio_webhooks, "WhatsAppNotificationService", Service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        invalid = await client.post(
            "/api/v1/webhooks/twilio/whatsapp/status",
            data=payload,
            headers={"X-Twilio-Signature": "invalid"},
        )
        valid = await client.post(
            "/api/v1/webhooks/twilio/whatsapp/status",
            data=payload,
            headers={"X-Twilio-Signature": signature},
        )

    assert invalid.status_code == 403
    assert invalid.json()["type"].endswith("twilio_signature_invalid")
    assert valid.status_code == 204
    assert database.commits == 1
    assert applied == [
        {
            "message_sid": "SM1234567890",
            "provider_status": "delivered",
            "parameters": payload,
        }
    ]
