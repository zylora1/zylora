from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import and_, distinct, exists, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.activation_models import (
    AcquisitionAttribution,
    ProductEvent,
    WebsiteDigestDelivery,
    WebsiteValueState,
    ZeroLeadCheckpoint,
)
from zylora_api.db.auth_models import User
from zylora_api.db.commerce_models import Subscription
from zylora_api.db.deployment_models import Domain
from zylora_api.db.lead_models import AnalyticsDailyRollup, Lead, TransactionalEmail
from zylora_api.db.website_models import Website
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.notifications.email import TransactionalEmailService
from zylora_api.modules.notifications.service import NotificationService
from zylora_api.modules.templates.service import problem

PRODUCT_EVENT_TYPES = frozenset(
    {
        "ACCOUNT_CREATED",
        "TEMPLATE_SELECTED",
        "WEBSITE_CREATED",
        "EDITOR_OPENED",
        "FIRST_EDIT",
        "AI_EDIT_REQUESTED",
        "AI_EDIT_SUCCEEDED",
        "AI_EDIT_FAILED",
        "SITE_PUBLISH_REQUESTED",
        "SITE_PUBLISHED",
        "SITE_PUBLISH_FAILED",
        "FIRST_VISITOR",
        "VISITOR_SESSION",
        "CHATBOT_CONVERSATION_STARTED",
        "CHATBOT_MESSAGE",
        "LEAD_FORM_OPENED",
        "LEAD_FORM_SUBMITTED",
        "LEAD_CREATED",
        "FIRST_LEAD",
        "CUSTOM_DOMAIN_CONNECTED",
        "PLAN_UPGRADE_STARTED",
        "PLAN_UPGRADED",
        "SUBSCRIPTION_CANCELLED",
        "SITE_UNPUBLISHED",
    }
)
SENSITIVE_PROPERTY_KEYS = frozenset(
    {
        "password",
        "token",
        "authorization",
        "email",
        "phone",
        "name",
        "enquiry",
        "message",
        "content",
    }
)
SOURCE_CATEGORIES = frozenset(
    {
        "DIRECT",
        "GOOGLE_ORGANIC",
        "OTHER_ORGANIC",
        "INSTAGRAM",
        "WHATSAPP_OUTREACH",
        "LINKEDIN",
        "YOUTUBE",
        "PARTNER",
        "FREELANCER",
        "OTHER",
    }
)


@dataclass(frozen=True)
class AttributionInput:
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    referrer: str | None = None
    landing_page: str | None = None


@dataclass(frozen=True)
class WebsiteValueMetrics:
    published_at: datetime | None
    first_visitor_at: datetime | None
    first_lead_at: datetime | None
    time_to_first_lead_seconds: int | None
    conversion_rate: float
    previous_page_views: int
    previous_leads: int
    page_view_change_percent: float | None
    lead_change_percent: float | None
    zero_lead_recommendations: list[str]


@dataclass(frozen=True)
class FunnelStep:
    key: str
    label: str
    count: int
    conversion_percent: float | None


@dataclass(frozen=True)
class RetentionMetric:
    days: int
    eligible_accounts: int
    retained_accounts: int
    retention_percent: float


@dataclass(frozen=True)
class AdminGrowthMetrics:
    range_days: int | None
    funnel: list[FunnelStep]
    active_value_sites_30d: int
    previous_active_value_sites_30d: int
    active_value_sites_change_percent: float | None
    retention: list[RetentionMetric]
    published_with_first_lead: int
    published_with_zero_leads: int
    paid_with_first_lead: int
    paid_with_zero_leads: int
    subscription_state_counts: dict[str, int]


class ProductAnalyticsService:
    """Canonical cross-lifecycle product analytics and value-state boundary."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_event(
        self,
        *,
        event_type: str,
        idempotency_key: str,
        user_id: UUID | None = None,
        website_id: UUID | None = None,
        properties: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> tuple[ProductEvent, bool]:
        if event_type not in PRODUCT_EVENT_TYPES:
            raise problem(422, "product_event_invalid", "Product event type is invalid.")
        if not 16 <= len(idempotency_key) <= 200:
            raise problem(422, "product_event_key_invalid", "Product event identifier is invalid.")
        safe_properties = properties or {}
        if len(safe_properties) > 20 or any(
            str(key).casefold() in SENSITIVE_PROPERTY_KEYS for key in safe_properties
        ):
            raise problem(
                422, "product_event_properties_invalid", "Product event properties are invalid."
            )
        encoded_size = sum(
            len(str(key)) + len(str(value)) for key, value in safe_properties.items()
        )
        if encoded_size > 4000:
            raise problem(
                422, "product_event_properties_invalid", "Product event properties are invalid."
            )
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"),
            {"value": f"product-event:{idempotency_key}"},
        )
        existing = await self.session.scalar(
            select(ProductEvent).where(ProductEvent.idempotency_key == idempotency_key)
        )
        if existing:
            return existing, True
        if website_id is not None:
            website = await self.session.get(Website, website_id)
            if not website or (user_id is not None and website.owner_user_id != user_id):
                raise problem(404, "website_not_found", "Website not found.")
        event = ProductEvent(
            event_type=event_type,
            idempotency_key=idempotency_key,
            user_id=user_id,
            website_id=website_id,
            properties=safe_properties,
            occurred_at=occurred_at or datetime.now(UTC),
        )
        self.session.add(event)
        return event, False

    async def capture_attribution(
        self,
        *,
        user_id: UUID,
        attribution: AttributionInput,
        country_code: str,
        signup_source: str,
    ) -> AcquisitionAttribution:
        country = self._country(country_code)
        existing = await self.session.scalar(
            select(AcquisitionAttribution).where(AcquisitionAttribution.user_id == user_id)
        )
        if existing:
            return existing
        values = {
            field: self._bounded(
                getattr(attribution, field), 1000 if field in {"referrer", "landing_page"} else 200
            )
            for field in (
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_content",
                "utm_term",
                "referrer",
                "landing_page",
            )
        }
        record = AcquisitionAttribution(
            user_id=user_id,
            normalized_source=self.normalize_source(attribution),
            signup_source=self._bounded(signup_source, 24) or "EMAIL",
            country_code=country,
            **values,
        )
        self.session.add(record)
        return record

    async def mark_published(self, website: Website, occurred_at: datetime | None = None) -> None:
        now = occurred_at or datetime.now(UTC)
        state = await self._value_state(website, now, lock=True)
        if state.owner_user_id != website.owner_user_id:
            # Ownership transfer begins a private value view for the new owner without
            # duplicating the Website-level FIRST_LEAD product event.
            state.owner_user_id = website.owner_user_id
            state.published_at = now
            state.first_visitor_at = None
            state.first_lead_at = None
        await self.record_event(
            event_type="SITE_PUBLISHED",
            idempotency_key=f"site-published:{website.id}",
            user_id=website.owner_user_id,
            website_id=website.id,
            occurred_at=now,
        )

    async def mark_first_visitor(self, website: Website, occurred_at: datetime) -> bool:
        state = await self._value_state(website, occurred_at, lock=True)
        if state.first_visitor_at is not None:
            return False
        state.first_visitor_at = occurred_at
        await self.record_event(
            event_type="FIRST_VISITOR",
            idempotency_key=f"first-visitor:{website.id}",
            user_id=website.owner_user_id,
            website_id=website.id,
            occurred_at=occurred_at,
        )
        return True

    async def mark_lead_created(self, lead: Lead) -> bool:
        website = await self.session.scalar(
            select(Website).where(Website.id == lead.website_id).with_for_update()
        )
        if not website or website.owner_user_id != lead.owner_user_id:
            raise problem(404, "website_not_found", "Website not found.")
        await self.record_event(
            event_type="LEAD_FORM_SUBMITTED",
            idempotency_key=f"lead-form-submitted-product:{lead.id}",
            user_id=lead.owner_user_id,
            website_id=lead.website_id,
            occurred_at=lead.captured_at,
        )
        await self.record_event(
            event_type="LEAD_CREATED",
            idempotency_key=f"lead-created:{lead.id}",
            user_id=lead.owner_user_id,
            website_id=lead.website_id,
            properties={"source": "FORM"},
            occurred_at=lead.captured_at,
        )
        state = await self._value_state(website, lead.captured_at, lock=True)
        if state.first_lead_at is not None:
            return False
        state.first_lead_at = lead.captured_at
        await self.record_event(
            event_type="FIRST_LEAD",
            idempotency_key=f"first-lead:{website.id}",
            user_id=lead.owner_user_id,
            website_id=lead.website_id,
            properties={"source": "FORM"},
            occurred_at=lead.captured_at,
        )
        return True

    async def website_value_metrics(
        self,
        *,
        owner_user_id: UUID,
        website_id: UUID,
        period_days: int,
        page_views: int,
        leads: int,
    ) -> WebsiteValueMetrics:
        if period_days not in {7, 30, 90}:
            raise problem(
                422, "analytics_period_invalid", "Analytics period must be 7, 30, or 90 days."
            )
        website = await self.session.scalar(
            select(Website).where(Website.id == website_id, Website.owner_user_id == owner_user_id)
        )
        if not website:
            raise problem(404, "website_not_found", "Website not found.")
        state = await self.session.scalar(
            select(WebsiteValueState).where(
                WebsiteValueState.website_id == website_id,
                WebsiteValueState.owner_user_id == owner_user_id,
            )
        )
        today = datetime.now(UTC).date()
        current_start = today - timedelta(days=period_days - 1)
        previous_start = current_start - timedelta(days=period_days)
        previous_end = current_start - timedelta(days=1)
        previous_page_views, previous_leads = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(AnalyticsDailyRollup.page_views), 0),
                    func.coalesce(func.sum(AnalyticsDailyRollup.leads), 0),
                ).where(
                    AnalyticsDailyRollup.website_id == website_id,
                    AnalyticsDailyRollup.owner_user_id == owner_user_id,
                    AnalyticsDailyRollup.bucket_date >= previous_start,
                    AnalyticsDailyRollup.bucket_date <= previous_end,
                )
            )
        ).one()
        recommendations = await self.zero_lead_recommendations(website)
        first_lead_seconds = None
        if state and state.first_lead_at:
            first_lead_seconds = max(
                0, int((state.first_lead_at - state.published_at).total_seconds())
            )
        return WebsiteValueMetrics(
            published_at=state.published_at if state else None,
            first_visitor_at=state.first_visitor_at if state else None,
            first_lead_at=state.first_lead_at if state else None,
            time_to_first_lead_seconds=first_lead_seconds,
            conversion_rate=round((leads / page_views * 100) if page_views else 0.0, 2),
            previous_page_views=int(previous_page_views),
            previous_leads=int(previous_leads),
            page_view_change_percent=self._change(page_views, int(previous_page_views)),
            lead_change_percent=self._change(leads, int(previous_leads)),
            zero_lead_recommendations=recommendations if leads == 0 else [],
        )

    async def admin_growth(self, range_days: int | None) -> AdminGrowthMetrics:
        if range_days not in {None, 7, 30, 90}:
            raise problem(422, "analytics_period_invalid", "Analytics period is invalid.")
        start = datetime.now(UTC) - timedelta(days=range_days) if range_days else None
        event_map = (
            ("ACCOUNT_CREATED", "Accounts created"),
            ("TEMPLATE_SELECTED", "Template selected"),
            ("FIRST_EDIT", "Editing started"),
            ("SITE_PUBLISHED", "Published"),
            ("FIRST_LEAD", "Received first lead"),
            ("PLAN_UPGRADED", "Paid"),
        )
        counts: list[int] = []
        for event_type, _ in event_map:
            statement = select(func.count(distinct(ProductEvent.user_id))).where(
                ProductEvent.event_type == event_type,
                ProductEvent.user_id.is_not(None),
            )
            if start:
                statement = statement.where(ProductEvent.occurred_at >= start)
            counts.append(int(await self.session.scalar(statement) or 0))
        retained_statement = select(func.count(distinct(Subscription.user_id))).where(
            Subscription.state == "ACTIVE",
            Subscription.created_at <= datetime.now(UTC) - timedelta(days=30),
        )
        if start:
            retained_statement = retained_statement.where(Subscription.created_at >= start)
        retained = int(await self.session.scalar(retained_statement) or 0)
        counts.append(retained)
        labels = [label for _, label in event_map] + ["Retained"]
        keys = [key for key, _ in event_map] + ["RETAINED"]
        funnel = [
            FunnelStep(
                key=key,
                label=label,
                count=count,
                conversion_percent=(
                    round(count / counts[index - 1] * 100, 2)
                    if index and counts[index - 1]
                    else (100.0 if index == 0 and count else None)
                ),
            )
            for index, (key, label, count) in enumerate(zip(keys, labels, counts, strict=True))
        ]
        now = datetime.now(UTC)
        active = await self._active_value_sites(now - timedelta(days=30), now)
        previous = await self._active_value_sites(
            now - timedelta(days=60), now - timedelta(days=30)
        )
        retention = [await self._retention(days) for days in (30, 60, 90)]
        published_filter = (
            Website.status == "PUBLISHED",
            Website.live_owner_user_id == WebsiteValueState.owner_user_id,
        )
        published_with_first = int(
            await self.session.scalar(
                select(func.count(WebsiteValueState.id))
                .join(Website, Website.id == WebsiteValueState.website_id)
                .where(*published_filter, WebsiteValueState.first_lead_at.is_not(None))
            )
            or 0
        )
        published_zero = int(
            await self.session.scalar(
                select(func.count(WebsiteValueState.id))
                .join(Website, Website.id == WebsiteValueState.website_id)
                .where(*published_filter, WebsiteValueState.first_lead_at.is_(None))
            )
            or 0
        )
        paid_user_ids = select(Subscription.user_id).where(Subscription.state == "ACTIVE")
        paid_with_first = int(
            await self.session.scalar(
                select(func.count(WebsiteValueState.id)).where(
                    WebsiteValueState.owner_user_id.in_(paid_user_ids),
                    WebsiteValueState.first_lead_at.is_not(None),
                )
            )
            or 0
        )
        paid_zero = int(
            await self.session.scalar(
                select(func.count(WebsiteValueState.id)).where(
                    WebsiteValueState.owner_user_id.in_(paid_user_ids),
                    WebsiteValueState.first_lead_at.is_(None),
                )
            )
            or 0
        )
        subscription_state_counts = {
            state: int(count)
            for state, count in (
                await self.session.execute(
                    select(Subscription.state, func.count(distinct(Subscription.user_id))).group_by(
                        Subscription.state
                    )
                )
            ).all()
        }
        return AdminGrowthMetrics(
            range_days=range_days,
            funnel=funnel,
            active_value_sites_30d=active,
            previous_active_value_sites_30d=previous,
            active_value_sites_change_percent=self._change(active, previous),
            retention=retention,
            published_with_first_lead=published_with_first,
            published_with_zero_leads=published_zero,
            paid_with_first_lead=paid_with_first,
            paid_with_zero_leads=paid_zero,
            subscription_state_counts=subscription_state_counts,
        )

    async def queue_monthly_digests(self, crypto: AuthCrypto, limit: int = 100) -> int:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        first_this_month = datetime.now(UTC).date().replace(day=1)
        previous_end = first_this_month - timedelta(days=1)
        previous_start = previous_end.replace(day=1)
        digest_month = previous_start.isoformat()[:7]
        deliveries = list(
            (
                await self.session.scalars(
                    select(WebsiteDigestDelivery)
                    .where(
                        WebsiteDigestDelivery.digest_month == digest_month,
                        WebsiteDigestDelivery.channel == "EMAIL",
                        WebsiteDigestDelivery.state == "PENDING",
                    )
                    .order_by(WebsiteDigestDelivery.created_at)
                    .limit(500)
                )
            ).all()
        )
        for delivery in deliveries:
            if not delivery.transactional_email_id:
                continue
            delivery_email = await self.session.get(
                TransactionalEmail, delivery.transactional_email_id
            )
            if delivery_email and delivery_email.state in {"SENT", "DELIVERED"}:
                delivery.state = "SENT"
                delivery.sent_at = delivery_email.sent_at
                delivery.safe_error_code = None
            elif delivery_email and delivery_email.state == "FAILED":
                delivery.state = "FAILED"
                delivery.safe_error_code = delivery_email.last_error_code or "digest_email_failed"

        websites = list(
            (
                await self.session.scalars(
                    select(Website)
                    .outerjoin(
                        WebsiteDigestDelivery,
                        and_(
                            WebsiteDigestDelivery.website_id == Website.id,
                            WebsiteDigestDelivery.digest_month == digest_month,
                            WebsiteDigestDelivery.channel == "EMAIL",
                        ),
                    )
                    .where(
                        Website.status == "PUBLISHED",
                        Website.live_owner_user_id.is_not(None),
                        WebsiteDigestDelivery.id.is_(None),
                    )
                    .order_by(Website.id)
                    .limit(limit)
                )
            ).all()
        )
        queued = 0
        for website in websites:
            owner = await self.session.get(User, website.owner_user_id)
            if not owner or owner.status != "ACTIVE":
                continue
            page_views, leads, conversations = (
                await self.session.execute(
                    select(
                        func.coalesce(func.sum(AnalyticsDailyRollup.page_views), 0),
                        func.coalesce(func.sum(AnalyticsDailyRollup.leads), 0),
                        func.coalesce(func.sum(AnalyticsDailyRollup.chatbot_conversations), 0),
                    ).where(
                        AnalyticsDailyRollup.website_id == website.id,
                        AnalyticsDailyRollup.owner_user_id == website.owner_user_id,
                        AnalyticsDailyRollup.bucket_date >= previous_start,
                        AnalyticsDailyRollup.bucket_date <= previous_end,
                    )
                )
            ).one()
            delivery = WebsiteDigestDelivery(
                website_id=website.id,
                owner_user_id=website.owner_user_id,
                digest_month=digest_month,
                channel="EMAIL",
                state="PENDING",
            )
            self.session.add(delivery)
            await self.session.flush()
            email = await TransactionalEmailService(self.session, crypto).queue(
                recipient_email=owner.display_email,
                recipient_user_id=owner.id,
                kind="MONTHLY_WEBSITE_DIGEST",
                resource_type="website_digest",
                resource_id=delivery.id,
                idempotency_key=f"website-digest:{website.id}:{digest_month}:email",
                subject=f"{website.display_name}: your {digest_month} Website results",
                body=(
                    f"Your Website this month\n\n{int(page_views)} visitors\n"
                    f"{int(leads)} enquiries\n{int(conversations)} chatbot conversations\n\n"
                    "Open Zylora Analytics for the complete measured trend."
                ),
                correlation_id=f"monthly-digest:{digest_month}",
            )
            delivery.transactional_email_id = email.id
            queued += 1
        return queued

    async def process_zero_lead_checkpoints(self, limit: int = 100) -> int:
        now = datetime.now(UTC)
        checkpoint_model = ZeroLeadCheckpoint
        missing_day_14 = ~exists(
            select(checkpoint_model.id).where(
                checkpoint_model.website_id == WebsiteValueState.website_id,
                checkpoint_model.publication_at == WebsiteValueState.published_at,
                checkpoint_model.checkpoint_days == 14,
            )
        )
        missing_day_30 = ~exists(
            select(checkpoint_model.id).where(
                checkpoint_model.website_id == WebsiteValueState.website_id,
                checkpoint_model.publication_at == WebsiteValueState.published_at,
                checkpoint_model.checkpoint_days == 30,
            )
        )
        states = list(
            (
                await self.session.scalars(
                    select(WebsiteValueState)
                    .join(Website, Website.id == WebsiteValueState.website_id)
                    .where(
                        Website.status == "PUBLISHED",
                        Website.live_owner_user_id == WebsiteValueState.owner_user_id,
                        WebsiteValueState.first_lead_at.is_(None),
                        WebsiteValueState.published_at <= now - timedelta(days=14),
                        or_(
                            missing_day_14,
                            and_(
                                WebsiteValueState.published_at <= now - timedelta(days=30),
                                missing_day_30,
                            ),
                        ),
                    )
                    .order_by(WebsiteValueState.published_at)
                    .limit(limit)
                )
            ).all()
        )
        notified = 0
        for state in states:
            age = (now - state.published_at).days
            for checkpoint_days in (14, 30):
                if age < checkpoint_days:
                    continue
                existing = await self.session.scalar(
                    select(ZeroLeadCheckpoint).where(
                        ZeroLeadCheckpoint.website_id == state.website_id,
                        ZeroLeadCheckpoint.publication_at == state.published_at,
                        ZeroLeadCheckpoint.checkpoint_days == checkpoint_days,
                    )
                )
                if existing:
                    continue
                checkpoint = ZeroLeadCheckpoint(
                    website_id=state.website_id,
                    owner_user_id=state.owner_user_id,
                    publication_at=state.published_at,
                    checkpoint_days=checkpoint_days,
                    state="PENDING",
                )
                self.session.add(checkpoint)
                await self.session.flush()
                notification = await NotificationService(self.session).create(
                    recipient_user_id=state.owner_user_id,
                    notification_type="ZERO_LEAD_CHECKPOINT",
                    resource_type="website",
                    resource_id=state.website_id,
                    dedupe_key=f"zero-lead:{state.website_id}:{state.published_at.isoformat()}:{checkpoint_days}",
                    data={"checkpoint_days": checkpoint_days},
                )
                await self.session.flush()
                checkpoint.notification_id = notification.id
                checkpoint.state = "NOTIFIED"
                notified += 1
        return notified

    async def zero_lead_recommendations(self, website: Website) -> list[str]:
        recommendations = [
            "Make the primary enquiry action clear near the top of the home page.",
            "Review the enquiry form and business contact information.",
            "Review the mobile layout and service descriptions.",
        ]
        custom_domain = await self.session.scalar(
            select(Domain.id).where(
                Domain.website_id == website.id,
                Domain.type == "CUSTOM",
                Domain.is_active.is_(True),
            )
        )
        if not custom_domain:
            recommendations[2] = (
                "Connect a custom domain and share the Website with existing customers."
            )
        return recommendations

    async def _value_state(
        self, website: Website, published_at: datetime, *, lock: bool
    ) -> WebsiteValueState:
        statement = select(WebsiteValueState).where(WebsiteValueState.website_id == website.id)
        if lock:
            statement = statement.with_for_update()
        state = await self.session.scalar(statement)
        if not state:
            state = WebsiteValueState(
                website_id=website.id,
                owner_user_id=website.owner_user_id,
                published_at=published_at,
            )
            self.session.add(state)
            await self.session.flush()
        return state

    async def _active_value_sites(self, start: datetime, end: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count(distinct(Lead.website_id)))
                .join(Website, Website.id == Lead.website_id)
                .where(
                    Lead.source == "FORM",
                    Lead.captured_at >= start,
                    Lead.captured_at < end,
                    Website.status == "PUBLISHED",
                    Website.live_owner_user_id.is_not(None),
                )
            )
            or 0
        )

    async def _retention(self, days: int) -> RetentionMetric:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        eligible = int(
            await self.session.scalar(
                select(func.count(User.id)).where(
                    User.account_type == "USER",
                    User.created_at <= cutoff,
                )
            )
            or 0
        )
        retained = int(
            await self.session.scalar(
                select(func.count(distinct(User.id)))
                .outerjoin(Subscription, Subscription.user_id == User.id)
                .where(
                    User.account_type == "USER",
                    User.created_at <= cutoff,
                    User.status == "ACTIVE",
                    (Subscription.state == "ACTIVE") | (Subscription.id.is_(None)),
                )
            )
            or 0
        )
        return RetentionMetric(
            days=days,
            eligible_accounts=eligible,
            retained_accounts=retained,
            retention_percent=round(retained / eligible * 100, 2) if eligible else 0.0,
        )

    @staticmethod
    def normalize_source(value: AttributionInput) -> str:
        source = (value.utm_source or "").strip().casefold()
        medium = (value.utm_medium or "").strip().casefold()
        referrer_host = urlparse(value.referrer or "").hostname or ""
        if source in {"instagram", "ig"}:
            return "INSTAGRAM"
        if source in {"whatsapp", "wa"}:
            return "WHATSAPP_OUTREACH"
        if source == "linkedin":
            return "LINKEDIN"
        if source == "youtube":
            return "YOUTUBE"
        if source == "partner":
            return "PARTNER"
        if source == "freelancer":
            return "FREELANCER"
        if "google." in referrer_host.casefold() and medium in {"", "organic"}:
            return "GOOGLE_ORGANIC"
        if medium == "organic":
            return "OTHER_ORGANIC"
        if not source and not referrer_host:
            return "DIRECT"
        return "OTHER"

    @staticmethod
    def _country(value: str | None) -> str:
        candidate = (value or "").strip().upper()
        return candidate if len(candidate) == 2 and candidate.isalpha() else "ZZ"

    @staticmethod
    def _bounded(value: str | None, limit: int) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate[:limit] if candidate else None

    @staticmethod
    def _change(current: int, previous: int) -> float | None:
        if previous == 0:
            return None if current == 0 else 100.0
        return round((current - previous) / previous * 100, 2)
