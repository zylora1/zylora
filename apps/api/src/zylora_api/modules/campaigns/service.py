from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.auth_models import User
from zylora_api.db.campaign_models import (
    Campaign,
    CampaignDeliveryEvent,
    CampaignRecipient,
    EmailSuppression,
)
from zylora_api.db.commerce_models import Subscription
from zylora_api.db.models import OutboxEvent
from zylora_api.db.website_models import Website
from zylora_api.modules.auth.delivery import TransactionalEmailProvider
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.service import problem

AudienceType = Literal[
    "ALL_USERS",
    "FREE_USERS",
    "PAID_USERS",
    "PLAN_USERS",
    "RECENT_USERS",
    "HAS_DRAFT",
    "NO_PUBLISHED_WEBSITE",
]

TERMINAL_RECIPIENT_STATES = {
    "SUPPRESSED",
    "SENT",
    "DELIVERED",
    "FAILED",
    "BOUNCED",
    "COMPLAINED",
    "UNSUBSCRIBED",
}


@dataclass(frozen=True)
class CampaignSummary:
    id: UUID
    name: str
    subject: str
    state: str
    audience_type: str
    audience_plan_code: str | None
    audience_snapshot_count: int
    scheduled_at: datetime | None
    created_at: datetime
    accepted_count: int = 0
    failed_count: int = 0
    suppressed_count: int = 0
    unsubscribed_count: int = 0


class CampaignService:
    """The only campaign aggregate writer; all delivery effects use durable outbox events."""

    def __init__(
        self, session: AsyncSession, crypto: AuthCrypto, *, public_origin: str = ""
    ) -> None:
        self.session = session
        self.crypto = crypto
        self.public_origin = public_origin.rstrip("/")

    async def create(
        self,
        *,
        actor_user_id: UUID,
        name: str,
        subject: str,
        body: str,
        audience_type: AudienceType,
        audience_plan_code: str | None = None,
    ) -> Campaign:
        self._validate_content(name, subject, body)
        self._validate_audience(audience_type, audience_plan_code)
        campaign = Campaign(
            created_by_user_id=actor_user_id,
            name=name.strip(),
            subject=subject.strip(),
            body=body.strip(),
            audience_type=audience_type,
            audience_plan_code=audience_plan_code,
        )
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def update(
        self,
        campaign_id: UUID,
        *,
        name: str,
        subject: str,
        body: str,
        audience_type: AudienceType,
        audience_plan_code: str | None,
    ) -> Campaign:
        campaign = await self._locked_campaign(campaign_id)
        if campaign.state != "DRAFT":
            raise problem(409, "campaign_not_editable", "Only draft campaigns can be edited.")
        self._validate_content(name, subject, body)
        self._validate_audience(audience_type, audience_plan_code)
        campaign.name, campaign.subject, campaign.body = name.strip(), subject.strip(), body.strip()
        campaign.audience_type, campaign.audience_plan_code = audience_type, audience_plan_code
        campaign.version += 1
        return campaign

    async def ready(self, campaign_id: UUID) -> Campaign:
        campaign = await self._locked_campaign(campaign_id)
        if campaign.state != "DRAFT":
            raise problem(409, "campaign_not_draft", "Only a draft campaign can be prepared.")
        self._validate_content(campaign.name, campaign.subject, campaign.body)
        campaign.state = "READY"
        campaign.version += 1
        return campaign

    async def schedule(self, campaign_id: UUID, when: datetime) -> Campaign:
        campaign = await self._locked_campaign(campaign_id)
        if campaign.state not in {"READY", "SCHEDULED"}:
            raise problem(
                409, "campaign_not_schedulable", "Prepare the campaign before scheduling it."
            )
        if when.tzinfo is None or when <= datetime.now(UTC):
            raise problem(
                422, "campaign_schedule_invalid", "Choose a future, timezone-aware send time."
            )
        campaign.state, campaign.scheduled_at = "SCHEDULED", when
        campaign.version += 1
        return campaign

    async def cancel(self, campaign_id: UUID) -> Campaign:
        campaign = await self._locked_campaign(campaign_id)
        if campaign.state not in {"DRAFT", "READY", "SCHEDULED", "PAUSED"}:
            raise problem(
                409, "campaign_not_cancellable", "This campaign can no longer be cancelled."
            )
        campaign.state = "CANCELLED"
        campaign.version += 1
        return campaign

    async def start(self, campaign_id: UUID, *, correlation_id: str) -> Campaign:
        campaign = await self._locked_campaign(campaign_id)
        if campaign.state not in {"READY", "SCHEDULED"}:
            raise problem(409, "campaign_not_sendable", "Prepare a campaign before sending it.")
        if (
            campaign.state == "SCHEDULED"
            and campaign.scheduled_at
            and campaign.scheduled_at > datetime.now(UTC)
        ):
            raise problem(409, "campaign_not_due", "This campaign is not due yet.")
        existing = await self.session.scalar(
            select(CampaignRecipient.id)
            .where(CampaignRecipient.campaign_id == campaign.id)
            .limit(1)
        )
        if existing:
            campaign.state = "SENDING"
            return campaign
        users = list((await self.session.scalars(self._audience_query(campaign))).all())
        if len(users) > 10_000:
            raise problem(
                422,
                "campaign_audience_too_large",
                "This audience exceeds the safe delivery batch size.",
            )
        now = datetime.now(UTC)
        for user in users:
            token = self.crypto.token()
            purpose = f"campaign-unsubscribe:{campaign.id}:{user.id}"
            suppressed = await self._is_suppressed(user.id)
            recipient = CampaignRecipient(
                campaign_id=campaign.id,
                recipient_user_id=user.id,
                recipient_ciphertext=self.crypto.encrypt(
                    user.display_email, purpose=f"{purpose}:recipient"
                ),
                unsubscribe_token_digest=self.crypto.digest(token, purpose=purpose),
                unsubscribe_token_ciphertext=self.crypto.encrypt(token, purpose=f"{purpose}:token"),
                idempotency_key=f"campaign:{campaign.id}:recipient:{user.id}",
                state="SUPPRESSED" if suppressed else "PENDING",
                suppression_reason="marketing_opt_out" if suppressed else None,
            )
            self.session.add(recipient)
            await self.session.flush()
            if not suppressed:
                self.session.add(
                    OutboxEvent(
                        aggregate_type="CAMPAIGN_RECIPIENT",
                        aggregate_id=recipient.id,
                        event_type="campaign.delivery_requested",
                        payload={"campaign_recipient_id": str(recipient.id)},
                        correlation_id=correlation_id,
                    )
                )
        campaign.audience_snapshot_count = len(users)
        campaign.state, campaign.started_at, campaign.scheduled_at = "SENDING", now, None
        campaign.version += 1
        if not users:
            campaign.state, campaign.completed_at = "COMPLETED", now
        return campaign

    async def process_outbox_event(
        self, event_id: UUID, provider: TransactionalEmailProvider
    ) -> OutboxEvent:
        event = await self.session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if not event:
            raise problem(404, "campaign_event_not_found", "Campaign delivery job not found.")
        if event.state == "PUBLISHED":
            return event
        if event.event_type != "campaign.delivery_requested":
            event.state, event.last_error_code = "FAILED", "unsupported_campaign_event"
            event.lease_owner = event.leased_until = None
            return event
        recipient = await self.session.scalar(
            select(CampaignRecipient)
            .where(CampaignRecipient.id == UUID(str(event.payload["campaign_recipient_id"])))
            .with_for_update()
        )
        if not recipient:
            event.state, event.last_error_code = "FAILED", "campaign_recipient_missing"
            event.lease_owner = event.leased_until = None
            return event
        if recipient.state in TERMINAL_RECIPIENT_STATES:
            event.state, event.published_at, event.last_error_code = (
                "PUBLISHED",
                datetime.now(UTC),
                None,
            )
            event.lease_owner = event.leased_until = None
            return event
        if await self._is_suppressed(recipient.recipient_user_id):
            recipient.state, recipient.suppression_reason = "SUPPRESSED", "marketing_opt_out"
            event.state, event.published_at, event.last_error_code = (
                "PUBLISHED",
                datetime.now(UTC),
                None,
            )
            event.lease_owner = event.leased_until = None
            await self._complete_if_finished(recipient.campaign_id)
            return event
        campaign = await self.session.scalar(
            select(Campaign).where(Campaign.id == recipient.campaign_id).with_for_update()
        )
        if not campaign or campaign.state != "SENDING":
            recipient.state, event.state, event.last_error_code = (
                "FAILED",
                "FAILED",
                "campaign_not_sending",
            )
            event.lease_owner = event.leased_until = None
            return event
        recipient.attempts += 1
        recipient.state = "SENDING"
        event.attempts += 1
        try:
            purpose = f"campaign-unsubscribe:{campaign.id}:{recipient.recipient_user_id}"
            email = self.crypto.decrypt(
                recipient.recipient_ciphertext, purpose=f"{purpose}:recipient"
            )
            token = self.crypto.decrypt(
                recipient.unsubscribe_token_ciphertext, purpose=f"{purpose}:token"
            )
            unsubscribe_url = f"{self.public_origin}/unsubscribe?token={token}"
            await provider.send_transactional(
                recipient=email,
                subject=campaign.subject,
                body=f"{campaign.body}\n\nUnsubscribe: {unsubscribe_url}",
            )
            now = datetime.now(UTC)
            recipient.state, recipient.sent_at, recipient.last_error_code = "SENT", now, None
            event.state, event.published_at, event.last_error_code = "PUBLISHED", now, None
            self.session.add(
                CampaignDeliveryEvent(
                    campaign_recipient_id=recipient.id,
                    event_type="ACCEPTED",
                    provider="SMTP",
                    provider_event_id=f"{recipient.id}:{recipient.attempts}",
                    metadata_json={},
                )
            )
        except Exception:
            if recipient.attempts >= 4:
                recipient.state, recipient.last_error_code = "FAILED", "campaign_delivery_failed"
                event.state, event.last_error_code = "FAILED", recipient.last_error_code
            else:
                retry_at = datetime.now(UTC) + timedelta(minutes=2 ** (recipient.attempts - 1))
                recipient.state, recipient.last_error_code = (
                    "PENDING",
                    "campaign_delivery_retry_wait",
                )
                event.state, event.available_at, event.last_error_code = (
                    "PENDING",
                    retry_at,
                    recipient.last_error_code,
                )
        finally:
            event.lease_owner = event.leased_until = None
        await self._complete_if_finished(recipient.campaign_id)
        return event

    async def unsubscribe(self, token: str) -> CampaignRecipient:
        if not 20 <= len(token) <= 200:
            raise problem(422, "unsubscribe_token_invalid", "This unsubscribe link is invalid.")
        candidates = list(
            (
                await self.session.scalars(
                    select(CampaignRecipient).where(
                        CampaignRecipient.state.not_in({"UNSUBSCRIBED"})
                    )
                )
            ).all()
        )
        recipient = next(
            (
                row
                for row in candidates
                if self.crypto.constant_time_equal(
                    row.unsubscribe_token_digest,
                    self.crypto.digest(
                        token,
                        purpose=f"campaign-unsubscribe:{row.campaign_id}:{row.recipient_user_id}",
                    ),
                )
            ),
            None,
        )
        if not recipient:
            raise problem(
                404, "unsubscribe_token_unknown", "This unsubscribe link is invalid or expired."
            )
        suppression = await self.session.scalar(
            select(EmailSuppression)
            .where(
                EmailSuppression.recipient_user_id == recipient.recipient_user_id,
                EmailSuppression.scope == "MARKETING",
            )
            .with_for_update()
        )
        if not suppression:
            self.session.add(
                EmailSuppression(
                    recipient_user_id=recipient.recipient_user_id,
                    scope="MARKETING",
                    reason="recipient_opt_out",
                    source="campaign_unsubscribe",
                )
            )
        recipient.state = "UNSUBSCRIBED"
        self.session.add(
            CampaignDeliveryEvent(
                campaign_recipient_id=recipient.id,
                event_type="UNSUBSCRIBED",
                provider="ZYLORA",
                provider_event_id=f"unsubscribe:{recipient.id}",
                metadata_json={},
            )
        )
        await self._complete_if_finished(recipient.campaign_id)
        return recipient

    async def list(self, limit: int = 50) -> builtins.list[CampaignSummary]:
        rows = list(
            (
                await self.session.scalars(
                    select(Campaign).order_by(Campaign.created_at.desc()).limit(limit)
                )
            ).all()
        )
        if not rows:
            return []
        state_counts = {
            (campaign_id, state): count
            for campaign_id, state, count in (
                await self.session.execute(
                    select(
                        CampaignRecipient.campaign_id,
                        CampaignRecipient.state,
                        func.count(CampaignRecipient.id),
                    )
                    .where(CampaignRecipient.campaign_id.in_([row.id for row in rows]))
                    .group_by(CampaignRecipient.campaign_id, CampaignRecipient.state)
                )
            ).all()
        }
        return [
            CampaignSummary(
                row.id,
                row.name,
                row.subject,
                row.state,
                row.audience_type,
                row.audience_plan_code,
                row.audience_snapshot_count,
                row.scheduled_at,
                row.created_at,
                accepted_count=state_counts.get((row.id, "SENT"), 0),
                failed_count=state_counts.get((row.id, "FAILED"), 0),
                suppressed_count=state_counts.get((row.id, "SUPPRESSED"), 0),
                unsubscribed_count=state_counts.get((row.id, "UNSUBSCRIBED"), 0),
            )
            for row in rows
        ]

    async def due_campaign_ids(self, limit: int) -> builtins.list[UUID]:
        now = datetime.now(UTC)
        return list(
            (
                await self.session.scalars(
                    select(Campaign.id)
                    .where(Campaign.state == "SCHEDULED", Campaign.scheduled_at <= now)
                    .order_by(Campaign.scheduled_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )

    async def _complete_if_finished(self, campaign_id: UUID) -> None:
        campaign = await self.session.scalar(
            select(Campaign).where(Campaign.id == campaign_id).with_for_update()
        )
        if not campaign or campaign.state != "SENDING":
            return
        unfinished = await self.session.scalar(
            select(CampaignRecipient.id)
            .where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.state.not_in(TERMINAL_RECIPIENT_STATES),
            )
            .limit(1)
        )
        if not unfinished:
            campaign.state = "COMPLETED"
            campaign.completed_at = datetime.now(UTC)
            campaign.version += 1

    async def _locked_campaign(self, campaign_id: UUID) -> Campaign:
        campaign = await self.session.scalar(
            select(Campaign).where(Campaign.id == campaign_id).with_for_update()
        )
        if not campaign:
            raise problem(404, "campaign_not_found", "Campaign not found.")
        return campaign

    async def _is_suppressed(self, user_id: UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(EmailSuppression.id)
                .where(
                    EmailSuppression.recipient_user_id == user_id,
                    EmailSuppression.scope.in_({"MARKETING", "ALL_EMAIL"}),
                )
                .limit(1)
            )
        )

    def _audience_query(self, campaign: Campaign) -> Select[tuple[User]]:
        query = select(User).where(User.account_type == "USER", User.status == "ACTIVE")
        active_subscription = exists(
            select(Subscription.id).where(
                Subscription.user_id == User.id,
                Subscription.state.in_({"ACTIVE", "RENEWAL_PENDING", "PAST_DUE"}),
                Subscription.current_period_end > datetime.now(UTC),
            )
        )
        if campaign.audience_type == "FREE_USERS":
            query = query.where(~active_subscription)
        elif campaign.audience_type == "PAID_USERS":
            query = query.where(active_subscription)
        elif campaign.audience_type == "PLAN_USERS":
            query = query.where(
                exists(
                    select(Subscription.id).where(
                        Subscription.user_id == User.id,
                        Subscription.state.in_({"ACTIVE", "RENEWAL_PENDING", "PAST_DUE"}),
                        Subscription.current_period_end > datetime.now(UTC),
                        Subscription.plan_code_snapshot == campaign.audience_plan_code,
                    )
                )
            )
        elif campaign.audience_type == "RECENT_USERS":
            query = query.where(User.created_at >= datetime.now(UTC) - timedelta(days=30))
        elif campaign.audience_type == "HAS_DRAFT":
            query = query.where(
                exists(
                    select(Website.id).where(
                        Website.owner_user_id == User.id, Website.status == "DRAFT"
                    )
                )
            )
        elif campaign.audience_type == "NO_PUBLISHED_WEBSITE":
            query = query.where(
                ~exists(
                    select(Website.id).where(
                        Website.owner_user_id == User.id, Website.status == "PUBLISHED"
                    )
                )
            )
        return query.order_by(User.created_at, User.id)

    @staticmethod
    def _validate_content(name: str, subject: str, body: str) -> None:
        if (
            not 1 <= len(name.strip()) <= 160
            or not 1 <= len(subject.strip()) <= 200
            or not 1 <= len(body.strip()) <= 20_000
        ):
            raise problem(
                422, "campaign_content_invalid", "Campaign name, subject, or body is invalid."
            )

    @staticmethod
    def _validate_audience(audience_type: str, plan_code: str | None) -> None:
        valid = {
            "ALL_USERS",
            "FREE_USERS",
            "PAID_USERS",
            "PLAN_USERS",
            "RECENT_USERS",
            "HAS_DRAFT",
            "NO_PUBLISHED_WEBSITE",
        }
        if (
            audience_type not in valid
            or (
                audience_type == "PLAN_USERS"
                and plan_code not in {"FREE", "BASIC", "GROWTH", "BUSINESS"}
            )
            or (audience_type != "PLAN_USERS" and plan_code is not None)
        ):
            raise problem(422, "campaign_audience_invalid", "Campaign audience is invalid.")
