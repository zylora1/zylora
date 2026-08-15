from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.commerce_models import NotificationQuotaAccount, NotificationQuotaLedger
from zylora_api.db.lead_models import AnalyticsEvent, Lead
from zylora_api.db.models import OutboxEvent
from zylora_api.db.website_models import Website
from zylora_api.db.whatsapp_models import WhatsAppNotificationSetting
from zylora_api.modules.commerce.service import SubscriptionService
from zylora_api.modules.leads.credits import CreditLedgerService
from zylora_api.modules.notifications.service import NotificationService
from zylora_api.modules.templates.service import problem


class NotificationQuotaService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reserve_whatsapp(self, user_id: UUID, country_code: str, operation_id: UUID) -> bool:
        duplicate = await self.session.scalar(
            select(NotificationQuotaLedger).where(
                NotificationQuotaLedger.user_id == user_id,
                NotificationQuotaLedger.channel == "WHATSAPP",
                NotificationQuotaLedger.operation_id == operation_id,
            )
        )
        if duplicate:
            return True
        effective = await SubscriptionService(self.session).effective(user_id, country_code)
        allowance = int(effective.entitlements["whatsapp_monthly_notifications"])
        account = await self.session.scalar(
            select(NotificationQuotaAccount)
            .where(
                NotificationQuotaAccount.user_id == user_id,
                NotificationQuotaAccount.channel == "WHATSAPP",
            )
            .with_for_update()
        )
        if not account:
            account = NotificationQuotaAccount(
                user_id=user_id,
                channel="WHATSAPP",
                used=0,
                allowance=allowance,
                period_start=effective.period_start,
                period_end=effective.period_end,
            )
            self.session.add(account)
            await self.session.flush()
        elif (
            account.period_start != effective.period_start
            or account.period_end != effective.period_end
        ):
            account.used = 0
            account.allowance = allowance
            account.period_start = effective.period_start
            account.period_end = effective.period_end
            account.version += 1
        else:
            account.allowance = max(allowance, account.used)
        if allowance == 0 or account.used >= allowance:
            return False
        account.used += 1
        account.version += 1
        self.session.add(
            NotificationQuotaLedger(
                user_id=user_id,
                channel="WHATSAPP",
                operation_id=operation_id,
                delta=1,
                resulting_used=account.used,
                reason="LEAD_NOTIFICATION",
            )
        )
        return True


@dataclass(frozen=True)
class LeadCaptureResult:
    lead: Lead
    duplicate: bool


class LeadService:
    """The sole Website-form Lead command path with transactional credit accounting."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def capture(
        self,
        *,
        website_id: UUID,
        source: str,
        idempotency_key: str,
        name: str,
        email: str | None,
        phone: str | None,
        enquiry: str,
        owner_country_code: str,
        correlation_id: str,
        page_path: str | None = None,
        consent: dict[str, Any] | None = None,
    ) -> LeadCaptureResult:
        if source != "FORM":
            raise problem(422, "invalid_lead_source", "Lead source is invalid.")
        if not 1 <= len(idempotency_key) <= 160:
            raise problem(422, "idempotency_key_required", "Provide a valid idempotency key.")
        normalized = {
            "name": name.strip(),
            "email": email.strip().lower() if email else None,
            "phone": phone.strip() if phone else None,
            "enquiry": enquiry.strip(),
            "page_path": page_path.strip() if page_path else None,
            "consent": consent or {},
        }
        if not normalized["name"] or not normalized["enquiry"]:
            raise problem(422, "invalid_lead", "Name and enquiry are required.")
        if len(normalized["name"]) > 160 or len(normalized["enquiry"]) > 10_000:
            raise problem(422, "invalid_lead", "Lead details are too long.")
        fingerprint = hashlib.sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        existing = await self._existing(website_id, source, idempotency_key)
        if existing:
            return self._duplicate_or_conflict(existing, fingerprint)
        website = await self.session.scalar(
            select(Website).where(Website.id == website_id).with_for_update()
        )
        if not website or website.status != "PUBLISHED" or not website.live_owner_user_id:
            raise problem(404, "published_website_not_found", "Published Website not found.")
        existing = await self._existing(website_id, source, idempotency_key)
        if existing:
            return self._duplicate_or_conflict(existing, fingerprint)
        credit_ledger = CreditLedgerService(self.session)
        await credit_ledger.ensure_capture_allowed(website.live_owner_user_id)
        lead = Lead(
            website_id=website.id,
            owner_user_id=website.live_owner_user_id,
            source=source,
            source_reference_id=None,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            name=str(normalized["name"]),
            email=str(normalized["email"]) if normalized["email"] else None,
            phone=str(normalized["phone"]) if normalized["phone"] else None,
            enquiry=str(normalized["enquiry"]),
            page_path=str(normalized["page_path"]) if normalized["page_path"] else None,
            consent=consent or {},
        )
        self.session.add(lead)
        await self.session.flush()
        await credit_ledger.consume_for_lead(lead)
        await NotificationService(self.session).create(
            recipient_user_id=lead.owner_user_id,
            notification_type="LEAD_CAPTURED",
            resource_type="lead",
            resource_id=lead.id,
            dedupe_key=f"lead:{lead.id}",
            data={"website_id": str(lead.website_id), "source": lead.source},
        )
        self.session.add_all(
            [
                AnalyticsEvent(
                    website_id=lead.website_id,
                    owner_user_id=lead.owner_user_id,
                    event_type="LEAD_CAPTURED",
                    idempotency_key=f"lead:{lead.id}",
                    properties={"source": lead.source},
                ),
                AnalyticsEvent(
                    website_id=lead.website_id,
                    owner_user_id=lead.owner_user_id,
                    event_type="LEAD_FORM_SUBMITTED",
                    idempotency_key=f"lead-form-submitted:{lead.id}",
                    properties={},
                ),
            ]
        )
        from zylora_api.modules.analytics.activation import ProductAnalyticsService

        await ProductAnalyticsService(self.session).mark_lead_created(lead)
        self.session.add(
            OutboxEvent(
                aggregate_type="LEAD",
                aggregate_id=lead.id,
                event_type="lead.owner_notification_requested",
                payload={
                    "lead_id": str(lead.id),
                    "website_id": str(website.id),
                    "owner_user_id": str(website.live_owner_user_id),
                },
                correlation_id=correlation_id,
            )
        )
        whatsapp_setting = await self.session.scalar(
            select(WhatsAppNotificationSetting).where(
                WhatsAppNotificationSetting.owner_user_id == website.live_owner_user_id,
                WhatsAppNotificationSetting.enabled.is_(True),
                WhatsAppNotificationSetting.status == "READY",
            )
        )
        queued = bool(whatsapp_setting) and await NotificationQuotaService(
            self.session
        ).reserve_whatsapp(website.live_owner_user_id, owner_country_code, lead.id)
        lead.whatsapp_notification_queued = queued
        if queued:
            self.session.add(
                OutboxEvent(
                    aggregate_type="LEAD",
                    aggregate_id=lead.id,
                    event_type="lead.whatsapp_notification_requested",
                    payload={
                        "lead_id": str(lead.id),
                        "website_id": str(website.id),
                        "owner_user_id": str(website.live_owner_user_id),
                    },
                    correlation_id=correlation_id,
                )
            )
        return LeadCaptureResult(lead, False)

    async def _existing(self, website_id: UUID, source: str, idempotency_key: str) -> Lead | None:
        return cast(
            Lead | None,
            await self.session.scalar(
                select(Lead).where(
                    Lead.website_id == website_id,
                    Lead.source == source,
                    Lead.idempotency_key == idempotency_key,
                )
            ),
        )

    @staticmethod
    def _duplicate_or_conflict(existing: Lead, fingerprint: str) -> LeadCaptureResult:
        if existing.request_fingerprint != fingerprint:
            raise problem(
                409,
                "idempotency_key_reused",
                "This idempotency key was used for another Lead payload.",
            )
        return LeadCaptureResult(existing, True)
