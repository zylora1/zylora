from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import User
from zylora_api.db.lead_models import TransactionalEmail
from zylora_api.db.models import OutboxEvent
from zylora_api.modules.auth.delivery import EmailSender, TransactionalEmailProvider
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.service import problem

MAX_ATTEMPTS = 4


class TransactionalEmailService:
    """Encrypted, idempotent transactional email jobs backed by the durable outbox."""

    def __init__(self, session: AsyncSession, crypto: AuthCrypto) -> None:
        self.session = session
        self.crypto = crypto

    async def queue(
        self,
        *,
        recipient_email: str,
        recipient_user_id: UUID | None,
        kind: str,
        resource_type: str,
        resource_id: UUID | None,
        idempotency_key: str,
        subject: str,
        body: str,
        correlation_id: str,
    ) -> TransactionalEmail:
        if not 16 <= len(idempotency_key) <= 200:
            raise problem(422, "transactional_email_key_invalid", "Email delivery key is invalid.")
        if not recipient_email or len(recipient_email) > 320 or not subject or len(subject) > 200:
            raise problem(422, "transactional_email_invalid", "Transactional email is invalid.")
        if not body or len(body) > 20_000:
            raise problem(422, "transactional_email_invalid", "Transactional email is invalid.")
        existing = await self.session.scalar(
            select(TransactionalEmail)
            .where(TransactionalEmail.idempotency_key == idempotency_key)
            .with_for_update()
        )
        if existing:
            return existing
        purpose = f"transactional-email:{idempotency_key}"
        email = TransactionalEmail(
            recipient_user_id=recipient_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            kind=kind,
            recipient_ciphertext=self.crypto.encrypt(
                recipient_email, purpose=f"{purpose}:recipient"
            ),
            content_ciphertext=self.crypto.encrypt(
                json.dumps({"subject": subject, "body": body}, separators=(",", ":")),
                purpose=f"{purpose}:content",
            ),
            idempotency_key=idempotency_key,
            state="QUEUED",
        )
        self.session.add(email)
        await self.session.flush()
        self.session.add(
            OutboxEvent(
                aggregate_type="TRANSACTIONAL_EMAIL",
                aggregate_id=email.id,
                event_type="transactional_email.send_requested",
                payload={"transactional_email_id": str(email.id)},
                correlation_id=correlation_id,
            )
        )
        return email

    async def process_outbox_event(
        self, event_id: UUID, provider: TransactionalEmailProvider
    ) -> OutboxEvent:
        event = await self.session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if not event:
            raise problem(404, "transactional_email_event_not_found", "Email job not found.")
        if event.state == "PUBLISHED":
            return event
        if event.event_type != "transactional_email.send_requested":
            event.state = "FAILED"
            event.last_error_code = "unsupported_transactional_email_event"
            event.lease_owner = None
            event.leased_until = None
            return event
        email = await self.session.scalar(
            select(TransactionalEmail)
            .where(TransactionalEmail.id == UUID(str(event.payload["transactional_email_id"])))
            .with_for_update()
        )
        if not email:
            event.state = "FAILED"
            event.last_error_code = "transactional_email_missing"
            event.lease_owner = None
            event.leased_until = None
            return event
        if email.state in {"SENT", "DELIVERED", "SUPPRESSED"}:
            event.state = "PUBLISHED"
            event.published_at = event.published_at or datetime.now(UTC)
            event.last_error_code = None
            event.lease_owner = None
            event.leased_until = None
            return event
        if email.state == "FAILED":
            event.state = "FAILED"
            event.last_error_code = email.last_error_code or "transactional_email_failed"
            event.lease_owner = None
            event.leased_until = None
            return event
        event.attempts += 1
        email.attempts += 1
        email.state = "SENDING"
        try:
            recipient, subject, body = self._decrypt(email)
            await provider.send_transactional(recipient=recipient, subject=subject, body=body)
            now = datetime.now(UTC)
            email.state = "SENT"
            email.sent_at = now
            email.last_error_code = None
            event.state = "PUBLISHED"
            event.published_at = now
            event.last_error_code = None
        except Exception:
            if email.attempts >= MAX_ATTEMPTS:
                email.state = "FAILED"
                email.last_error_code = "transactional_email_delivery_failed"
                event.state = "FAILED"
                event.last_error_code = email.last_error_code
            else:
                delay = timedelta(minutes=2 ** (email.attempts - 1))
                email.state = "RETRY_WAIT"
                email.next_attempt_at = datetime.now(UTC) + delay
                email.last_error_code = "transactional_email_retry_wait"
                event.state = "PENDING"
                event.available_at = email.next_attempt_at
                event.last_error_code = email.last_error_code
        finally:
            event.lease_owner = None
            event.leased_until = None
        return event

    def _decrypt(self, email: TransactionalEmail) -> tuple[str, str, str]:
        purpose = f"transactional-email:{email.idempotency_key}"
        recipient = self.crypto.decrypt(email.recipient_ciphertext, purpose=f"{purpose}:recipient")
        payload = json.loads(
            self.crypto.decrypt(email.content_ciphertext, purpose=f"{purpose}:content")
        )
        subject = payload.get("subject") if isinstance(payload, dict) else None
        body = payload.get("body") if isinstance(payload, dict) else None
        if not isinstance(subject, str) or not isinstance(body, str):
            raise ValueError("transactional email payload is invalid")
        return recipient, subject, body


class TransactionalEmailSender(EmailSender):
    """Compatibility adapter that moves existing auth messages onto Phase 11's durable queue."""

    def __init__(self, session: AsyncSession, crypto: AuthCrypto, settings: Settings) -> None:
        self.session = session
        self.crypto = crypto
        self.settings = settings

    async def send_verification(self, *, email: str, code: str) -> None:
        await self._queue_auth(
            email=email,
            value=code,
            kind="AUTH_VERIFICATION",
            subject="Verify your Zylora account",
            body=f"Your Zylora verification code is {code}. It expires in 15 minutes.",
        )

    async def send_password_reset(self, *, email: str, token: str) -> None:
        origin = self.settings.allowed_origins[0].rstrip("/")
        reset_url = f"{origin}/reset-password?token={quote(token, safe='')}"
        await self._queue_auth(
            email=email,
            value=token,
            kind="AUTH_PASSWORD_RESET",
            subject="Reset your Zylora password",
            body=(f"Use this one-time Zylora password reset link within 15 minutes: {reset_url}"),
        )

    async def _queue_auth(
        self, *, email: str, value: str, kind: str, subject: str, body: str
    ) -> None:
        user = await self.session.scalar(select(User).where(User.display_email == email))
        digest = hashlib.sha256(value.encode()).hexdigest()
        await TransactionalEmailService(self.session, self.crypto).queue(
            recipient_email=email,
            recipient_user_id=user.id if user else None,
            kind=kind,
            resource_type="user",
            resource_id=user.id if user else None,
            idempotency_key=f"{kind.casefold()}:{user.id if user else digest}:{digest}",
            subject=subject,
            body=body,
            correlation_id="auth-transactional-email",
        )
        await self.session.commit()
