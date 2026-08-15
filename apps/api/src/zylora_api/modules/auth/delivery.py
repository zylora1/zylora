from __future__ import annotations

import hashlib
from email.message import EmailMessage
from typing import Any, Protocol

import aiosmtplib
import httpx
from zylora_api.core.config import Settings


class EmailSender(Protocol):
    async def send_verification(self, *, email: str, code: str) -> None: ...

    async def send_password_reset(self, *, email: str, token: str) -> None: ...


class TransactionalEmailProvider(Protocol):
    async def send_transactional(self, *, recipient: str, subject: str, body: str) -> None: ...


class SMTPEmailSender:
    """Production SMTP adapter; provider credentials and mail bodies are never logged."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send_verification(self, *, email: str, code: str) -> None:
        await self.send_transactional(
            recipient=email,
            subject="Verify your Zylora account",
            body=f"Your Zylora verification code is {code}. It expires in 15 minutes.",
        )

    async def send_password_reset(self, *, email: str, token: str) -> None:
        reset_url = f"{self._settings.allowed_origins[0]}/reset-password?token={token}"
        await self.send_transactional(
            recipient=email,
            subject="Reset your Zylora password",
            body=f"Use this one-time link within 15 minutes: {reset_url}",
        )

    async def send_transactional(self, *, recipient: str, subject: str, body: str) -> None:
        if not self._settings.smtp_host:
            raise RuntimeError("SMTP is not configured")
        message = EmailMessage()
        message["From"] = self._settings.smtp_from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        await aiosmtplib.send(
            message,
            hostname=self._settings.smtp_host,
            port=self._settings.smtp_port,
            username=self._settings.smtp_username,
            password=self._settings.smtp_password,
            start_tls=self._settings.smtp_start_tls,
            use_tls=self._settings.smtp_port == 465,
            timeout=10,
        )


class ResendEmailSender:
    """Resend HTTPS adapter; credentials, recipients, and message bodies are never logged."""

    _endpoint = "https://api.resend.com/emails"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    async def send_verification(self, *, email: str, code: str) -> None:
        await self.send_transactional(
            recipient=email,
            subject="Verify your Zylora account",
            body=f"Your Zylora verification code is {code}. It expires in 15 minutes.",
        )

    async def send_password_reset(self, *, email: str, token: str) -> None:
        reset_url = f"{self._settings.allowed_origins[0]}/reset-password?token={token}"
        await self.send_transactional(
            recipient=email,
            subject="Reset your Zylora password",
            body=f"Use this one-time link within 15 minutes: {reset_url}",
        )

    async def send_transactional(self, *, recipient: str, subject: str, body: str) -> None:
        api_key = self._settings.resend_api_key
        if not api_key:
            raise RuntimeError("Resend is not configured")
        digest = hashlib.sha256("\0".join((recipient, subject, body)).encode("utf-8")).hexdigest()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Idempotency-Key": f"zylora-{digest}",
        }
        payload = {
            "from": self._settings.smtp_from_email,
            "to": [recipient],
            "subject": subject,
            "text": body,
        }
        if self._client is not None:
            response = await self._client.post(self._endpoint, headers=headers, json=payload)
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self._endpoint, headers=headers, json=payload)
        response.raise_for_status()
        self._validate_success_response(response)

    @staticmethod
    def _validate_success_response(response: httpx.Response) -> None:
        try:
            payload: Any = response.json()
        except ValueError as error:
            raise RuntimeError("Resend returned an invalid success response") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise RuntimeError("Resend returned an invalid success response")


def transactional_email_provider_for(settings: Settings) -> TransactionalEmailProvider:
    if settings.email_provider == "resend":
        return ResendEmailSender(settings)
    return SMTPEmailSender(settings)
