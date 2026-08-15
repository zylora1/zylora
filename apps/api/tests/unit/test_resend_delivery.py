from __future__ import annotations

import hashlib
import json

import httpx
import pytest
from zylora_api.core.config import Settings
from zylora_api.modules.auth.delivery import (
    ResendEmailSender,
    SMTPEmailSender,
    transactional_email_provider_for,
)


@pytest.mark.asyncio
async def test_resend_adapter_sends_plain_text_with_stable_idempotency() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"id": "email-id"})

    settings = Settings(
        _env_file=None,
        environment="test",
        storage_provider="memory",
        email_provider="resend",
        resend_api_key="resend-test-key",
        smtp_from_email="Zylora <no-reply@example.com>",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sender = ResendEmailSender(settings, client)
        await sender.send_transactional(
            recipient="developer@example.com",
            subject="Verify your Zylora account",
            body="Your verification code is 123456.",
        )

    request = captured["request"]
    assert isinstance(request, httpx.Request)
    assert request.url == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == "Bearer resend-test-key"
    expected_digest = hashlib.sha256(
        b"developer@example.com\0Verify your Zylora account\0Your verification code is 123456."
    ).hexdigest()
    assert request.headers["Idempotency-Key"] == f"zylora-{expected_digest}"
    assert json.loads(request.content) == {
        "from": "Zylora <no-reply@example.com>",
        "to": ["developer@example.com"],
        "subject": "Verify your Zylora account",
        "text": "Your verification code is 123456.",
    }


@pytest.mark.asyncio
async def test_resend_adapter_does_not_fake_success() -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        storage_provider="memory",
        email_provider="resend",
        resend_api_key="resend-test-key",
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(503, json={"message": "down"}))
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await ResendEmailSender(settings, client).send_transactional(
                recipient="developer@example.com", subject="Test", body="Message"
            )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    ) as client:
        with pytest.raises(RuntimeError, match="invalid success response"):
            await ResendEmailSender(settings, client).send_transactional(
                recipient="developer@example.com", subject="Test", body="Message"
            )


def test_email_provider_factory_selects_configured_transport() -> None:
    smtp = Settings(_env_file=None)
    resend = Settings(
        _env_file=None,
        email_provider="resend",
        resend_api_key="resend-test-key",
    )

    assert isinstance(transactional_email_provider_for(smtp), SMTPEmailSender)
    assert isinstance(transactional_email_provider_for(resend), ResendEmailSender)
