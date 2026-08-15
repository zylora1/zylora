from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.auth_models import User
from zylora_api.db.lead_models import AnalyticsDailyRollup, AnalyticsEvent
from zylora_api.db.website_models import Website
from zylora_api.modules.templates.service import problem

EVENT_TYPES = frozenset(
    {
        "PAGE_VIEW",
        "LEAD_FORM_OPENED",
        "LEAD_FORM_SUBMITTED",
        "LEAD_CAPTURED",
        "CHATBOT_CONVERSATION_STARTED",
        "CHATBOT_MESSAGE",
        "WEBSITE_PUBLISHED",
    }
)


@dataclass(frozen=True)
class EventRecordResult:
    event: AnalyticsEvent
    duplicate: bool


@dataclass(frozen=True)
class DashboardMetrics:
    website_id: UUID | None
    timezone: str
    period_days: int
    has_published_website: bool
    has_meaningful_data: bool
    page_views: int
    sessions: int
    visitors: int
    leads: int
    lead_form_opens: int
    lead_form_submissions: int
    form_leads: int
    chatbot_leads: int
    chatbot_conversations: int
    chatbot_messages: int
    conversions: int
    points: list[AnalyticsDailyRollup]


class AnalyticsService:
    """Canonical real-event ingestion and background rollup boundary."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        website_id: UUID,
        event_type: str,
        idempotency_key: str,
        owner_user_id: UUID | None = None,
        properties: dict[str, Any] | None = None,
        page_path: str | None = None,
        visitor_hash: bytes | None = None,
        session_hash: bytes | None = None,
        occurred_at: datetime | None = None,
    ) -> EventRecordResult:
        if event_type not in EVENT_TYPES:
            raise problem(422, "analytics_event_invalid", "Analytics event type is invalid.")
        if not 16 <= len(idempotency_key) <= 160:
            raise problem(
                422, "analytics_idempotency_required", "Provide a valid analytics event identifier."
            )
        if page_path is not None and (not page_path.startswith("/") or len(page_path) > 1024):
            raise problem(422, "analytics_page_path_invalid", "Analytics page path is invalid.")
        if visitor_hash is not None and len(visitor_hash) != 32:
            raise problem(422, "analytics_visitor_invalid", "Analytics visitor value is invalid.")
        if session_hash is not None and len(session_hash) != 32:
            raise problem(422, "analytics_session_invalid", "Analytics session value is invalid.")
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"),
            {"value": f"analytics-event:{website_id}:{idempotency_key}"},
        )
        existing = await self.session.scalar(
            select(AnalyticsEvent).where(
                AnalyticsEvent.website_id == website_id,
                AnalyticsEvent.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return EventRecordResult(existing, True)
        website = await self.session.scalar(
            select(Website).where(Website.id == website_id).with_for_update()
        )
        resolved_owner = website.live_owner_user_id if website else None
        if not website or website.status != "PUBLISHED" or not resolved_owner:
            raise problem(404, "published_website_not_found", "Published Website not found.")
        if owner_user_id is not None and owner_user_id != resolved_owner:
            raise problem(404, "published_website_not_found", "Published Website not found.")
        event = AnalyticsEvent(
            website_id=website.id,
            owner_user_id=resolved_owner,
            event_type=event_type,
            idempotency_key=idempotency_key,
            properties=properties or {},
            page_path=page_path,
            visitor_hash=visitor_hash,
            session_hash=session_hash,
            occurred_at=occurred_at or datetime.now(UTC),
        )
        self.session.add(event)
        await self.session.flush()
        from zylora_api.modules.analytics.activation import ProductAnalyticsService

        lifecycle = ProductAnalyticsService(self.session)
        if event_type == "PAGE_VIEW":
            await lifecycle.mark_first_visitor(website, event.occurred_at)
        elif event_type in {
            "CHATBOT_CONVERSATION_STARTED",
            "CHATBOT_MESSAGE",
            "LEAD_FORM_OPENED",
        }:
            await lifecycle.record_event(
                event_type=event_type,
                idempotency_key=f"website-event:{website.id}:{idempotency_key}",
                user_id=resolved_owner,
                website_id=website.id,
                properties=properties or {},
                occurred_at=event.occurred_at,
            )
        elif event_type == "WEBSITE_PUBLISHED":
            await lifecycle.mark_published(website, event.occurred_at)
        return EventRecordResult(event, False)

    async def refresh_website(
        self,
        *,
        website_id: UUID,
        owner_user_id: UUID,
        timezone: str,
        start_date: date,
        end_date: date,
    ) -> list[AnalyticsDailyRollup]:
        zone = self._timezone(timezone)
        website = await self.session.scalar(
            select(Website).where(
                Website.id == website_id,
                Website.owner_user_id == owner_user_id,
                Website.live_owner_user_id == owner_user_id,
                Website.status == "PUBLISHED",
            )
        )
        if not website:
            raise problem(404, "published_website_not_found", "Published Website not found.")
        if end_date < start_date:
            raise problem(422, "analytics_range_invalid", "Analytics date range is invalid.")
        if (end_date - start_date).days > 400:
            raise problem(422, "analytics_range_invalid", "Analytics range is too large.")
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"),
            {"value": f"analytics-rollup:{website_id}:{timezone}:{start_date}:{end_date}"},
        )
        rollups: list[AnalyticsDailyRollup] = []
        candidate = start_date
        while candidate <= end_date:
            rollups.append(
                await self._refresh_day(
                    website_id=website_id,
                    owner_user_id=owner_user_id,
                    timezone=timezone,
                    zone=zone,
                    bucket_date=candidate,
                )
            )
            candidate += timedelta(days=1)
        return rollups

    async def refresh_recent(self, limit: int = 100) -> int:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        rows = list(
            (
                await self.session.execute(
                    select(AnalyticsEvent.website_id, AnalyticsEvent.owner_user_id)
                    .join(Website, Website.id == AnalyticsEvent.website_id)
                    .where(
                        Website.status == "PUBLISHED",
                        Website.live_owner_user_id == AnalyticsEvent.owner_user_id,
                    )
                    .distinct()
                    .order_by(AnalyticsEvent.website_id)
                    .limit(limit)
                )
            ).all()
        )
        refreshed = 0
        for website_id, owner_user_id in rows:
            owner = await self.session.get(User, owner_user_id)
            if not owner or owner.account_type != "USER":
                continue
            zone = self._timezone(owner.timezone)
            today = datetime.now(zone).date()
            await self.refresh_website(
                website_id=website_id,
                owner_user_id=owner_user_id,
                timezone=owner.timezone,
                start_date=today - timedelta(days=1),
                end_date=today,
            )
            refreshed += 1
        return refreshed

    async def dashboard(
        self,
        *,
        owner_user_id: UUID,
        timezone: str,
        period_days: int,
        website_id: UUID | None = None,
    ) -> DashboardMetrics:
        if period_days not in {7, 30, 90}:
            raise problem(
                422, "analytics_period_invalid", "Analytics period must be 7, 30, or 90 days."
            )
        self._timezone(timezone)
        websites_query = select(Website.id).where(
            Website.owner_user_id == owner_user_id,
            Website.status == "PUBLISHED",
            Website.live_owner_user_id == owner_user_id,
        )
        if website_id is not None:
            websites_query = websites_query.where(Website.id == website_id)
        website_ids = list((await self.session.scalars(websites_query)).all())
        if website_id is not None and not website_ids:
            raise problem(404, "website_not_found", "Website not found.")
        if not website_ids:
            return DashboardMetrics(
                website_id=website_id,
                timezone=timezone,
                period_days=period_days,
                has_published_website=False,
                has_meaningful_data=False,
                page_views=0,
                sessions=0,
                visitors=0,
                leads=0,
                lead_form_opens=0,
                lead_form_submissions=0,
                form_leads=0,
                chatbot_leads=0,
                chatbot_conversations=0,
                chatbot_messages=0,
                conversions=0,
                points=[],
            )
        end_date = datetime.now(self._timezone(timezone)).date()
        start_date = end_date - timedelta(days=period_days - 1)
        rows = list(
            (
                await self.session.scalars(
                    select(AnalyticsDailyRollup)
                    .where(
                        AnalyticsDailyRollup.owner_user_id == owner_user_id,
                        AnalyticsDailyRollup.website_id.in_(website_ids),
                        AnalyticsDailyRollup.timezone == timezone,
                        AnalyticsDailyRollup.bucket_date >= start_date,
                        AnalyticsDailyRollup.bucket_date <= end_date,
                    )
                    .order_by(AnalyticsDailyRollup.bucket_date)
                )
            ).all()
        )
        totals = {
            field: sum(int(getattr(item, field)) for item in rows)
            for field in (
                "page_views",
                "sessions",
                "visitors",
                "leads",
                "lead_form_opens",
                "lead_form_submissions",
                "form_leads",
                "chatbot_leads",
                "chatbot_conversations",
                "chatbot_messages",
                "conversions",
            )
        }
        return DashboardMetrics(
            website_id=website_id or website_ids[0],
            timezone=timezone,
            period_days=period_days,
            has_published_website=True,
            has_meaningful_data=bool(
                totals["page_views"]
                or totals["leads"]
                or totals["chatbot_conversations"]
                or totals["chatbot_messages"]
            ),
            points=rows,
            **totals,
        )

    async def _refresh_day(
        self,
        *,
        website_id: UUID,
        owner_user_id: UUID,
        timezone: str,
        zone: ZoneInfo,
        bucket_date: date,
    ) -> AnalyticsDailyRollup:
        start = datetime.combine(bucket_date, time.min, tzinfo=zone).astimezone(UTC)
        end = datetime.combine(bucket_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(
            UTC
        )
        events = list(
            (
                await self.session.scalars(
                    select(AnalyticsEvent).where(
                        AnalyticsEvent.website_id == website_id,
                        AnalyticsEvent.owner_user_id == owner_user_id,
                        AnalyticsEvent.occurred_at >= start,
                        AnalyticsEvent.occurred_at < end,
                    )
                )
            ).all()
        )
        metrics = self._metrics(events)
        rollup = await self.session.scalar(
            select(AnalyticsDailyRollup)
            .where(
                AnalyticsDailyRollup.website_id == website_id,
                AnalyticsDailyRollup.timezone == timezone,
                AnalyticsDailyRollup.bucket_date == bucket_date,
            )
            .with_for_update()
        )
        if not rollup:
            rollup = AnalyticsDailyRollup(
                website_id=website_id,
                owner_user_id=owner_user_id,
                timezone=timezone,
                bucket_date=bucket_date,
                **metrics,
            )
            self.session.add(rollup)
        else:
            for field, value in metrics.items():
                setattr(rollup, field, value)
            rollup.refreshed_at = datetime.now(UTC)
        return rollup

    @staticmethod
    def _metrics(events: list[AnalyticsEvent]) -> dict[str, int]:
        page_views = [event for event in events if event.event_type == "PAGE_VIEW"]
        leads = [event for event in events if event.event_type == "LEAD_CAPTURED"]
        return {
            "event_count": len(events),
            "page_views": len(page_views),
            "sessions": len({event.session_hash for event in page_views if event.session_hash}),
            "visitors": len({event.visitor_hash for event in page_views if event.visitor_hash}),
            "leads": len(leads),
            "lead_form_opens": sum(event.event_type == "LEAD_FORM_OPENED" for event in events),
            "lead_form_submissions": sum(
                event.event_type == "LEAD_FORM_SUBMITTED" for event in events
            ),
            "form_leads": sum(event.properties.get("source") == "FORM" for event in leads),
            "chatbot_leads": sum(event.properties.get("source") == "CHATBOT" for event in leads),
            "chatbot_conversations": sum(
                event.event_type == "CHATBOT_CONVERSATION_STARTED" for event in events
            ),
            "chatbot_messages": sum(event.event_type == "CHATBOT_MESSAGE" for event in events),
            "conversions": len(leads),
        }

    @staticmethod
    def _timezone(candidate: str) -> ZoneInfo:
        try:
            return ZoneInfo(candidate)
        except ZoneInfoNotFoundError as error:
            raise problem(
                422, "analytics_timezone_invalid", "Analytics timezone is invalid."
            ) from error
