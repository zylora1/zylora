from __future__ import annotations

from email.message import EmailMessage
from typing import Protocol

import aiosmtplib
from zylora_api.core.config import Settings


class EmailSender(Protocol):
    async def send_verification(self, *, email: str, code: str) -> None: ...

    async def send_password_reset(self, *, email: str, token: str) -> None: ...


class SMTPEmailSender:
    """Production-capable SMTP adapter. Secret values are never returned or logged."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send_verification(self, *, email: str, code: str) -> None:
        await self._send(
            recipient=email,
            subject="Verify your Zylora account",
            body=f"Your Zylora verification code is {code}. It expires in 15 minutes.",
        )

    async def send_password_reset(self, *, email: str, token: str) -> None:
        reset_url = f"{self._settings.allowed_origins[0]}/reset-password?token={token}"
        await self._send(
            recipient=email,
            subject="Reset your Zylora password",
            body=f"Use this one-time link within 15 minutes: {reset_url}",
        )

    async def _send(self, *, recipient: str, subject: str, body: str) -> None:
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
