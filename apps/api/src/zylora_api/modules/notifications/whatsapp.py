from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import phonenumbers
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.base.exceptions import TwilioRestException  # type: ignore[import-untyped]
from twilio.http.async_http_client import AsyncTwilioHttpClient  # type: ignore[import-untyped]
from twilio.rest import Client  # type: ignore[import-untyped]
from zylora_api.core.config import Settings
from zylora_api.db.lead_models import Lead
from zylora_api.db.models import OutboxEvent
from zylora_api.db.website_models import Website
from zylora_api.db.whatsapp_models import (
    WhatsAppCallbackEvent,
    WhatsAppNotification,
    WhatsAppNotificationSetting,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.commerce.quotas import NotificationQuotaService
from zylora_api.modules.commerce.service import SubscriptionService
from zylora_api.modules.templates.service import problem

logger = logging.getLogger("zylora.whatsapp")

MAX_ATTEMPTS = 4
STATUS_STATE = {
    "accepted": "SENT",
    "scheduled": "SENT",
    "queued": "SENT",
    "sending": "SENT",
    "sent": "SENT",
    "delivered": "DELIVERED",
    "read": "READ",
    "failed": "FAILED",
    "undelivered": "FAILED",
}
STATE_RANK = {
    "QUEUED": 0,
    "SENDING": 0,
    "RETRY_WAIT": 0,
    "SENT": 1,
    "FAILED": 2,
    "DELIVERED": 3,
    "READ": 4,
    "SUPPRESSED": 4,
}


class WhatsAppProviderError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class WhatsAppSendResult:
    message_sid: str
    provider_status: str


class WhatsAppProvider(Protocol):
    async def send_template(
        self,
        *,
        to_e164: str,
        content_sid: str,
        variables: dict[str, str],
        status_callback: str,
    ) -> WhatsAppSendResult: ...


class TwilioWhatsAppProvider:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if not settings.whatsapp_enabled:
            raise WhatsAppProviderError("whatsapp_not_configured", retryable=False)
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise WhatsAppProviderError("whatsapp_not_configured", retryable=False)
        self.settings = settings
        self.client = client or Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            http_client=AsyncTwilioHttpClient(timeout=settings.twilio_timeout_seconds),
        )

    async def send_template(
        self,
        *,
        to_e164: str,
        content_sid: str,
        variables: dict[str, str],
        status_callback: str,
    ) -> WhatsAppSendResult:
        kwargs: dict[str, Any] = {
            "to": f"whatsapp:{to_e164}",
            "content_sid": content_sid,
            "content_variables": json.dumps(variables, separators=(",", ":")),
            "status_callback": status_callback,
        }
        if self.settings.twilio_messaging_service_sid:
            kwargs["messaging_service_sid"] = self.settings.twilio_messaging_service_sid
        elif self.settings.twilio_whatsapp_from:
            sender = self.settings.twilio_whatsapp_from
            kwargs["from_"] = sender if sender.startswith("whatsapp:") else f"whatsapp:{sender}"
        try:
            message = await self.client.messages.create_async(**kwargs)
        except TwilioRestException as error:
            status = int(error.status or 0)
            retryable = status == 429 or status >= 500 or status == 0
            raise WhatsAppProviderError(
                "twilio_retryable" if retryable else "twilio_rejected",
                retryable=retryable,
            ) from error
        except (OSError, TimeoutError) as error:
            raise WhatsAppProviderError("twilio_unavailable", retryable=True) from error
        sid = str(getattr(message, "sid", ""))
        if not sid.startswith("SM"):
            raise WhatsAppProviderError("twilio_invalid_response", retryable=True)
        return WhatsAppSendResult(
            message_sid=sid,
            provider_status=str(getattr(message, "status", "queued") or "queued"),
        )


def normalize_e164(value: str, country_code: str) -> str:
    try:
        parsed = phonenumbers.parse(value.strip(), country_code.upper())
    except phonenumbers.NumberParseException as error:
        raise problem(
            422, "whatsapp_number_invalid", "Enter a valid WhatsApp phone number."
        ) from error
    if not phonenumbers.is_valid_number(parsed):
        raise problem(422, "whatsapp_number_invalid", "Enter a valid WhatsApp phone number.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class WhatsAppNotificationService:
    def __init__(
        self,
        session: AsyncSession,
        crypto: AuthCrypto,
        settings: Settings,
        provider: WhatsAppProvider | None = None,
    ) -> None:
        self.session = session
        self.crypto = crypto
        self.settings = settings
        self.provider = provider

    async def setting_for(self, owner_user_id: UUID) -> WhatsAppNotificationSetting | None:
        return cast(
            WhatsAppNotificationSetting | None,
            await self.session.scalar(
                select(WhatsAppNotificationSetting).where(
                    WhatsAppNotificationSetting.owner_user_id == owner_user_id
                )
            ),
        )

    async def update_setting(
        self,
        *,
        owner_user_id: UUID,
        phone_number: str | None,
        country_code: str,
        enabled: bool,
        consent: bool,
    ) -> WhatsAppNotificationSetting:
        if enabled and not consent:
            raise problem(
                422,
                "whatsapp_consent_required",
                "Confirm that you are authorized to receive notifications at this number.",
            )
        if enabled and not self.settings.whatsapp_enabled:
            raise problem(503, "whatsapp_not_configured", "WhatsApp delivery is not configured.")
        effective = await SubscriptionService(self.session).effective(
            owner_user_id, country_code.upper()
        )
        if enabled and int(effective.entitlements["whatsapp_monthly_notifications"]) <= 0:
            raise problem(
                403,
                "whatsapp_not_entitled",
                "Your current plan does not include WhatsApp notifications.",
            )
        setting = await self.session.scalar(
            select(WhatsAppNotificationSetting)
            .where(WhatsAppNotificationSetting.owner_user_id == owner_user_id)
            .with_for_update()
        )
        normalized = (
            normalize_e164(phone_number, country_code)
            if phone_number and phone_number.strip()
            else None
        )
        if not setting and not normalized:
            raise problem(422, "whatsapp_number_invalid", "Enter a valid WhatsApp phone number.")
        now = datetime.now(UTC)
        if not setting:
            assert normalized is not None
            setting = WhatsAppNotificationSetting(
                id=uuid4(),
                owner_user_id=owner_user_id,
                phone_ciphertext=b"",
                phone_hash=b"",
                phone_last4=normalized[-4:],
                country_code=country_code.upper(),
                consented_at=now if consent else None,
            )
            self.session.add(setting)
        if normalized:
            purpose = f"whatsapp-setting:{setting.id}:phone"
            setting.phone_ciphertext = self.crypto.encrypt(normalized, purpose=purpose)
            setting.phone_hash = self.crypto.digest(normalized, purpose="whatsapp-recipient")
            setting.phone_last4 = normalized[-4:]
            setting.country_code = country_code.upper()
        setting.enabled = enabled
        setting.status = "READY" if enabled else "DISABLED"
        if consent:
            setting.consented_at = now
        setting.version += 1
        return setting

    async def queue_test(
        self, *, owner_user_id: UUID, country_code: str, correlation_id: str
    ) -> WhatsAppNotification:
        setting = await self.setting_for(owner_user_id)
        if not setting or not setting.enabled:
            raise problem(409, "whatsapp_setting_disabled", "Enable WhatsApp notifications first.")
        if not self.settings.whatsapp_enabled or not self.settings.twilio_test_template_content_sid:
            raise problem(503, "whatsapp_not_configured", "WhatsApp delivery is not configured.")
        notification_id = uuid4()
        reserved = await NotificationQuotaService(self.session).reserve_whatsapp(
            owner_user_id, country_code, notification_id
        )
        if not reserved:
            raise problem(
                403, "whatsapp_quota_exhausted", "Your WhatsApp notification quota is exhausted."
            )
        notification = WhatsAppNotification(
            id=notification_id,
            owner_user_id=owner_user_id,
            setting_id=setting.id,
            kind="TEST",
            template_content_sid=self.settings.twilio_test_template_content_sid,
            idempotency_key=f"whatsapp-test:{notification_id}",
            state="QUEUED",
        )
        self.session.add(notification)
        self.session.add(
            OutboxEvent(
                aggregate_type="WHATSAPP_NOTIFICATION",
                aggregate_id=notification.id,
                event_type="whatsapp.notification_requested",
                payload={"notification_id": str(notification.id)},
                correlation_id=correlation_id,
            )
        )
        setting.last_tested_at = datetime.now(UTC)
        logger.info(
            "whatsapp_enqueued",
            extra={
                "notification_id": str(notification.id),
                "event_type": "whatsapp.enqueued",
                "correlation_id": correlation_id,
                "outcome": "queued",
            },
        )
        return notification

    async def process_outbox_event(self, event_id: UUID) -> OutboxEvent:
        event = await self.session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if not event:
            raise problem(404, "whatsapp_event_not_found", "WhatsApp job not found.")
        if event.state == "PUBLISHED":
            return event
        if event.event_type not in {
            "lead.whatsapp_notification_requested",
            "whatsapp.notification_requested",
        }:
            event.lease_owner = None
            event.leased_until = None
            event.state = "FAILED"
            event.last_error_code = "whatsapp_event_unsupported"
            return event
        try:
            notification = await self._resolve_notification(event)
        except WhatsAppProviderError as error:
            event.attempts += 1
            if error.retryable and event.attempts < MAX_ATTEMPTS:
                event.state = "PENDING"
                event.available_at = datetime.now(UTC) + timedelta(
                    minutes=2 ** (event.attempts - 1)
                )
                event.last_error_code = "whatsapp_retry_wait"
            else:
                event.state = "FAILED"
                event.last_error_code = error.code
            event.lease_owner = None
            event.leased_until = None
            return event
        if not notification:
            event.state = "PUBLISHED"
            event.published_at = datetime.now(UTC)
            event.last_error_code = None
            event.lease_owner = None
            event.leased_until = None
            return event
        if notification.state in {"SENT", "DELIVERED", "READ", "SUPPRESSED"}:
            event.state = "PUBLISHED"
            event.published_at = event.published_at or datetime.now(UTC)
            event.lease_owner = None
            event.leased_until = None
            return event
        event.attempts += 1
        notification.attempts += 1
        notification.state = "SENDING"
        setting = await self.session.get(WhatsAppNotificationSetting, notification.setting_id)
        if not setting or not setting.enabled:
            notification.state = "SUPPRESSED"
            event.state = "PUBLISHED"
            event.published_at = datetime.now(UTC)
            event.lease_owner = None
            event.leased_until = None
            return event
        try:
            provider = self.provider or TwilioWhatsAppProvider(self.settings)
            recipient = self.crypto.decrypt(
                setting.phone_ciphertext, purpose=f"whatsapp-setting:{setting.id}:phone"
            )
            variables = await self._variables(notification)
            callback = (self.settings.twilio_status_callback_base_url or "").rstrip(
                "/"
            ) + "/api/v1/webhooks/twilio/whatsapp/status"
            result = await provider.send_template(
                to_e164=recipient,
                content_sid=notification.template_content_sid,
                variables=variables,
                status_callback=callback,
            )
            now = datetime.now(UTC)
            notification.provider_message_sid = result.message_sid
            notification.provider_status = result.provider_status[:40]
            notification.state = "SENT"
            notification.sent_at = now
            notification.failure_code = None
            notification.failure_detail_safe = None
            event.state = "PUBLISHED"
            event.published_at = now
            event.last_error_code = None
            setting.status = "READY"
            logger.info(
                "whatsapp_sent",
                extra={
                    "notification_id": str(notification.id),
                    "event_type": "whatsapp.sent",
                    "correlation_id": event.correlation_id,
                    "provider_message_sid": result.message_sid,
                    "attempt": notification.attempts,
                    "outcome": "sent",
                },
            )
        except WhatsAppProviderError as error:
            notification.failure_code = error.code
            notification.failure_detail_safe = "WhatsApp delivery could not be completed."
            if error.retryable and notification.attempts < MAX_ATTEMPTS:
                notification.state = "RETRY_WAIT"
                notification.next_attempt_at = datetime.now(UTC) + timedelta(
                    minutes=2 ** (notification.attempts - 1)
                )
                event.state = "PENDING"
                event.available_at = notification.next_attempt_at
                event.last_error_code = "whatsapp_retry_wait"
            else:
                notification.state = "FAILED"
                notification.failed_at = datetime.now(UTC)
                event.state = "FAILED"
                event.last_error_code = error.code
                setting.status = "NEEDS_ATTENTION"
            logger.warning(
                "whatsapp_delivery_failed",
                extra={
                    "notification_id": str(notification.id),
                    "event_type": "whatsapp.failed",
                    "correlation_id": event.correlation_id,
                    "attempt": notification.attempts,
                    "outcome": notification.state.casefold(),
                    "safe_error_code": error.code,
                },
            )
        finally:
            event.lease_owner = None
            event.leased_until = None
        return event

    async def _resolve_notification(self, event: OutboxEvent) -> WhatsAppNotification | None:
        if event.event_type == "whatsapp.notification_requested":
            return cast(
                WhatsAppNotification | None,
                await self.session.scalar(
                    select(WhatsAppNotification)
                    .where(WhatsAppNotification.id == UUID(str(event.payload["notification_id"])))
                    .with_for_update()
                ),
            )
        lead_id = UUID(str(event.payload["lead_id"]))
        existing = await self.session.scalar(
            select(WhatsAppNotification)
            .where(WhatsAppNotification.idempotency_key == f"whatsapp-lead:{lead_id}")
            .with_for_update()
        )
        if existing:
            return existing
        lead = await self.session.get(Lead, lead_id)
        if not lead:
            raise WhatsAppProviderError("lead_missing", retryable=False)
        setting = await self.setting_for(lead.owner_user_id)
        if not setting or not setting.enabled:
            return None
        if not self.settings.twilio_lead_template_content_sid:
            raise WhatsAppProviderError("whatsapp_not_configured", retryable=False)
        notification = WhatsAppNotification(
            owner_user_id=lead.owner_user_id,
            website_id=lead.website_id,
            lead_id=lead.id,
            setting_id=setting.id,
            kind="LEAD_OWNER_ALERT",
            template_content_sid=self.settings.twilio_lead_template_content_sid,
            idempotency_key=f"whatsapp-lead:{lead.id}",
            state="QUEUED",
        )
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def _variables(self, notification: WhatsAppNotification) -> dict[str, str]:
        if notification.kind == "TEST":
            return {
                "1": "Zylora test",
                "2": "Test lead",
                "3": "test@zylora.example",
                "4": "WhatsApp notifications are ready.",
            }
        if not notification.lead_id:
            raise WhatsAppProviderError("lead_missing", retryable=False)
        lead = await self.session.get(Lead, notification.lead_id)
        website = await self.session.get(Website, notification.website_id)
        if not lead or not website:
            raise WhatsAppProviderError("lead_missing", retryable=False)
        return {
            "1": website.display_name[:120],
            "2": lead.name[:120],
            "3": (lead.email or "Not provided")[:200],
            "4": " ".join(lead.enquiry.split())[:500],
        }

    async def apply_callback(
        self, *, message_sid: str, provider_status: str, parameters: dict[str, str]
    ) -> WhatsAppNotification | None:
        normalized_status = provider_status.casefold()
        mapped = STATUS_STATE.get(normalized_status)
        digest = hashlib.sha256(
            json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        duplicate = await self.session.scalar(
            select(WhatsAppCallbackEvent).where(WhatsAppCallbackEvent.event_digest == digest)
        )
        if duplicate:
            return (
                await self.session.get(WhatsAppNotification, duplicate.notification_id)
                if duplicate.notification_id
                else None
            )
        notification = await self.session.scalar(
            select(WhatsAppNotification)
            .where(WhatsAppNotification.provider_message_sid == message_sid)
            .with_for_update()
        )
        outcome = "notification_not_found"
        if notification and mapped:
            outcome = "ignored_out_of_order"
            if STATE_RANK[mapped] >= STATE_RANK[notification.state]:
                now = datetime.now(UTC)
                notification.state = mapped
                notification.provider_status = normalized_status[:40]
                if mapped == "DELIVERED":
                    notification.delivered_at = now
                elif mapped == "READ":
                    notification.read_at = now
                elif mapped == "FAILED":
                    notification.failed_at = now
                    notification.failure_code = "twilio_delivery_failed"
                    notification.failure_detail_safe = "WhatsApp delivery could not be completed."
                outcome = "applied"
                setting = await self.session.get(
                    WhatsAppNotificationSetting, notification.setting_id
                )
                if setting and mapped == "FAILED":
                    setting.status = "NEEDS_ATTENTION"
                elif setting:
                    setting.status = "READY"
        self.session.add(
            WhatsAppCallbackEvent(
                notification_id=notification.id if notification else None,
                provider_message_sid=message_sid,
                provider_status=normalized_status[:40],
                event_digest=digest,
                signature_verified=True,
                processing_outcome=outcome,
            )
        )
        logger.info(
            "whatsapp_callback_processed",
            extra={
                "notification_id": str(notification.id) if notification else None,
                "event_type": "whatsapp.callback",
                "provider_message_sid": message_sid,
                "outcome": outcome,
            },
        )
        return notification
