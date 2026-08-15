from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.auth_models import User
from zylora_api.db.lead_models import Lead
from zylora_api.db.models import OutboxEvent
from zylora_api.db.website_models import Website
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.notifications.email import TransactionalEmailService
from zylora_api.modules.templates.service import problem


class LeadOwnerNotificationService:
    """Turns the Lead domain intent into the existing encrypted email delivery job."""

    def __init__(self, session: AsyncSession, crypto: AuthCrypto) -> None:
        self.session = session
        self.crypto = crypto

    async def process_outbox_event(self, event_id: UUID) -> OutboxEvent:
        event = await self.session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if not event:
            raise problem(
                404, "lead_notification_event_not_found", "Lead notification job not found."
            )
        if event.state == "PUBLISHED":
            return event
        if event.event_type != "lead.owner_notification_requested":
            event.state = "FAILED"
            event.last_error_code = "lead_notification_event_unsupported"
            return event
        event.attempts += 1
        lead = await self.session.get(Lead, UUID(str(event.payload["lead_id"])))
        if not lead:
            event.state = "FAILED"
            event.last_error_code = "lead_missing"
            return event
        owner = await self.session.get(User, lead.owner_user_id)
        website = await self.session.get(Website, lead.website_id)
        if not owner or not website:
            event.state = "FAILED"
            event.last_error_code = "lead_owner_missing"
            return event
        await TransactionalEmailService(self.session, self.crypto).queue(
            recipient_email=owner.display_email,
            recipient_user_id=owner.id,
            kind="LEAD_OWNER_ALERT",
            resource_type="lead",
            resource_id=lead.id,
            idempotency_key=f"lead-owner-email:{lead.id}",
            subject=f"New lead from {website.display_name}"[:200],
            body=(
                f"Name: {lead.name}\n"
                f"Email: {lead.email or 'Not provided'}\n"
                f"Message: {' '.join(lead.enquiry.split())[:2000]}\n\n"
                "Open Zylora to view the lead."
            ),
            correlation_id=event.correlation_id,
        )
        event.state = "PUBLISHED"
        event.published_at = datetime.now(UTC)
        event.last_error_code = None
        event.lease_owner = None
        event.leased_until = None
        return event
