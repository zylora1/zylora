from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import User
from zylora_api.db.lead_models import (
    AnalyticsEvent,
    Notification,
    TransactionalEmail,
)
from zylora_api.db.models import OutboxEvent
from zylora_api.db.session import get_engine
from zylora_api.db.website_models import Website
from zylora_api.modules.analytics.service import AnalyticsService
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.notifications.email import (
    TransactionalEmailSender,
    TransactionalEmailService,
)
from zylora_api.modules.notifications.service import NotificationService
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.websites.service import WebsiteService


class CapturingTransactionalProvider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[tuple[str, str, str]] = []

    async def send_transactional(self, *, recipient: str, subject: str, body: str) -> None:
        if self.fail:
            raise RuntimeError("provider is unavailable")
        self.messages.append((recipient, subject, body))


def document(name: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "registry_version": "1.0.0",
        "metadata": {"name": name, "description": "Phase 11 Website", "language": "en"},
        "theme": {
            "primary": "#315C4A",
            "accent": "#D77A45",
            "surface": "#FFFFFF",
            "ink": "#17201E",
            "heading_font": "MANROPE",
            "body_font": "INTER",
        },
        "assets": [],
        "pages": [
            {
                "id": "home-page",
                "slug": "home",
                "label": "Home",
                "parent_page_id": None,
                "sort_order": 0,
                "is_home": True,
                "show_in_navigation": True,
                "status": "ACTIVE",
                "seo": {"title": name, "description": "Phase 11 Website"},
                "components": [
                    {
                        "id": "hero",
                        "type": "HERO",
                        "props": {"heading": name, "body": "Measured Website activity."},
                        "children": [],
                        "responsive": {},
                        "interactions": [],
                    }
                ],
            }
        ],
        "features": [],
        "requirements": [],
        "provenance": "CURATED",
    }


async def published_site(
    session: AsyncSession, *, timezone: str = "Asia/Kolkata"
) -> tuple[User, Website]:
    suffix = uuid4().hex
    owner = User(
        account_type="USER",
        normalized_email=f"phase11-{suffix}@example.com",
        display_email=f"phase11-{suffix}@example.com",
        status="ACTIVE",
        verified_at=datetime.now(UTC),
        billing_country_code="ZZ",
        timezone=timezone,
    )
    session.add(owner)
    await session.flush()
    templates = TemplateService(session, AuthCrypto("phase11-secret-long-enough-for-tests"))
    template = await templates.create(
        TemplateCreateRequest(
            slug=f"phase11-{suffix}",
            name="Phase 11 Site",
            summary="Phase 11 test template.",
            category_slug=f"phase11-category-{suffix}",
            category_name="Phase 11",
            category_description="Phase 11 test category.",
            tags=[f"phase11-{suffix}"],
            featured_order=100,
        ),
        owner.id,
    )
    await templates.add_version(template.id, document("Phase 11 Site"), owner.id)
    assert (await templates.validate(template.id, 1, owner.id)).status == "VALIDATED"
    await templates.approve(template.id, 1)
    await templates.publish(template.id, 1)
    website = await WebsiteService(session).instantiate(template.slug, owner.id)
    website.status = "PUBLISHED"
    website.live_owner_user_id = owner.id
    website.published_version_id = website.current_version_id
    await session.flush()
    return owner, website


@pytest.mark.integration
async def test_analytics_events_rollup_timezone_idempotency_and_owner_isolation() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await published_site(session)
        analytics = AnalyticsService(session)
        first = await analytics.record(
            website_id=website.id,
            owner_user_id=owner.id,
            event_type="PAGE_VIEW",
            idempotency_key="phase11-page-view-0001",
            page_path="/services",
            visitor_hash=b"v" * 32,
            session_hash=b"s" * 32,
        )
        duplicate = await analytics.record(
            website_id=website.id,
            owner_user_id=owner.id,
            event_type="PAGE_VIEW",
            idempotency_key="phase11-page-view-0001",
            page_path="/services",
            visitor_hash=b"v" * 32,
            session_hash=b"s" * 32,
        )
        assert duplicate.duplicate is True
        assert duplicate.event.id == first.event.id
        await analytics.record(
            website_id=website.id,
            owner_user_id=owner.id,
            event_type="LEAD_CAPTURED",
            idempotency_key="phase11-lead-captured-0001",
            properties={"source": "FORM"},
        )
        await analytics.record(
            website_id=website.id,
            owner_user_id=owner.id,
            event_type="CHATBOT_CONVERSATION_STARTED",
            idempotency_key="phase11-chat-started-0001",
        )
        await analytics.record(
            website_id=website.id,
            owner_user_id=owner.id,
            event_type="CHATBOT_MESSAGE",
            idempotency_key="phase11-chat-message-0001",
        )
        historical = await analytics.record(
            website_id=website.id,
            owner_user_id=owner.id,
            event_type="PAGE_VIEW",
            idempotency_key="phase11-timezone-boundary",
            page_path="/about",
            occurred_at=datetime(2026, 1, 1, 19, 0, tzinfo=UTC),
        )
        assert historical.duplicate is False
        january = await analytics.refresh_website(
            website_id=website.id,
            owner_user_id=owner.id,
            timezone="Asia/Kolkata",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )
        assert [item.page_views for item in january] == [0, 1]
        today = datetime.now(UTC).astimezone().date()
        await analytics.refresh_website(
            website_id=website.id,
            owner_user_id=owner.id,
            timezone="Asia/Kolkata",
            start_date=today,
            end_date=today,
        )
        dashboard = await analytics.dashboard(
            owner_user_id=owner.id,
            timezone="Asia/Kolkata",
            period_days=30,
            website_id=website.id,
        )
        assert dashboard.has_meaningful_data is True
        assert dashboard.page_views == 1
        assert dashboard.sessions == 1
        assert dashboard.visitors == 1
        assert dashboard.leads == 1
        assert dashboard.form_leads == 1
        assert dashboard.chatbot_conversations == 1
        assert dashboard.chatbot_messages == 1
        assert await analytics.refresh_recent(1) == 1
        assert (
            await session.scalar(
                select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.website_id == website.id)
            )
            == 5
        )
        other_owner, other_website = await published_site(session)
        with pytest.raises(AuthProblem, match="Published Website not found"):
            await analytics.record(
                website_id=other_website.id,
                owner_user_id=owner.id,
                event_type="PAGE_VIEW",
                idempotency_key="phase11-cross-owner-event",
            )
        with pytest.raises(AuthProblem, match="Published Website not found"):
            await analytics.refresh_website(
                website_id=website.id,
                owner_user_id=other_owner.id,
                timezone="Asia/Kolkata",
                start_date=today,
                end_date=today,
            )
        other_dashboard = await analytics.dashboard(
            owner_user_id=other_owner.id,
            timezone="Asia/Kolkata",
            period_days=30,
        )
        assert other_dashboard.page_views == 0
        assert other_dashboard.points == []
        await session.commit()


@pytest.mark.integration
async def test_notifications_are_deduplicated_paginated_and_private() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, _ = await published_site(session)
        other_owner, _ = await published_site(session)
        notifications = NotificationService(session)
        resource_id = uuid4()
        first = await notifications.create(
            recipient_user_id=owner.id,
            notification_type="LEAD_CAPTURED",
            resource_type="lead",
            resource_id=resource_id,
            dedupe_key="phase11-lead-notification",
            data={"source": "FORM"},
        )
        duplicate = await notifications.create(
            recipient_user_id=owner.id,
            notification_type="LEAD_CAPTURED",
            resource_type="lead",
            resource_id=resource_id,
            dedupe_key="phase11-lead-notification",
            data={"source": "FORM"},
        )
        assert duplicate.id == first.id
        for index in range(2):
            await notifications.create(
                recipient_user_id=owner.id,
                notification_type="WEBSITE_PUBLISHED",
                resource_type="website",
                resource_id=uuid4(),
                dedupe_key=f"phase11-published-{index}",
            )
        await notifications.create(
            recipient_user_id=other_owner.id,
            notification_type="WEBSITE_PUBLISHED",
            resource_type="website",
            resource_id=uuid4(),
            dedupe_key="phase11-other-owner",
        )
        records, unread, cursor = await notifications.page_for_user(
            recipient_user_id=owner.id, limit=2
        )
        assert len(records) == 2
        assert unread == 3
        assert cursor is not None
        marked = await notifications.mark_read(first.id, owner.id)
        assert marked.state == "READ"
        assert marked.read_at is not None
        with pytest.raises(AuthProblem, match="Notification not found"):
            await notifications.mark_read(first.id, other_owner.id)
        assert (
            await session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.recipient_user_id == owner.id
                )
            )
            == 3
        )
        await session.commit()


@pytest.mark.integration
async def test_transactional_email_is_encrypted_idempotent_retryable_and_auth_compatible() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    crypto = AuthCrypto("phase11-transactional-secret-long-enough")
    settings = Settings(environment="test", storage_provider="memory", _env_file=None)
    async with factory() as session:
        owner, _ = await published_site(session)
        service = TransactionalEmailService(session, crypto)
        first_key = f"phase11-transactional-email-{uuid4().hex}"
        retry_key = f"phase11-transactional-email-{uuid4().hex}"
        queued = await service.queue(
            recipient_email=owner.display_email,
            recipient_user_id=owner.id,
            kind="WEBSITE_PUBLISHED",
            resource_type="website",
            resource_id=uuid4(),
            idempotency_key=first_key,
            subject="Your Website is live",
            body="The Website has been published.",
            correlation_id="phase11-email",
        )
        duplicate = await service.queue(
            recipient_email=owner.display_email,
            recipient_user_id=owner.id,
            kind="WEBSITE_PUBLISHED",
            resource_type="website",
            resource_id=queued.resource_id,
            idempotency_key=first_key,
            subject="Your Website is live",
            body="The Website has been published.",
            correlation_id="phase11-email-duplicate",
        )
        assert duplicate.id == queued.id
        assert owner.display_email.encode() not in queued.recipient_ciphertext
        assert b"Website has been published" not in queued.content_ciphertext
        event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == queued.id).with_for_update()
        )
        assert event is not None
        assert event.state == "PENDING"
        assert queued.state == "QUEUED"
        provider = CapturingTransactionalProvider()
        processed = await service.process_outbox_event(event.id, provider)
        assert processed.state == "PUBLISHED"
        assert queued.state == "SENT"
        assert provider.messages == [
            (owner.display_email, "Your Website is live", "The Website has been published.")
        ]
        assert (await service.process_outbox_event(event.id, provider)).state == "PUBLISHED"
        assert len(provider.messages) == 1
        retry = await service.queue(
            recipient_email=owner.display_email,
            recipient_user_id=owner.id,
            kind="DOMAIN_STATE",
            resource_type="website",
            resource_id=uuid4(),
            idempotency_key=retry_key,
            subject="Domain update",
            body="A retry is expected.",
            correlation_id="phase11-email-retry",
        )
        retry_event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == retry.id).with_for_update()
        )
        assert retry_event is not None
        assert (
            await service.process_outbox_event(
                retry_event.id, CapturingTransactionalProvider(fail=True)
            )
        ).state == "PENDING"
        assert retry.state == "RETRY_WAIT"
        sender = TransactionalEmailSender(session, crypto, settings)
        await sender.send_password_reset(email=owner.display_email, token="phase11-reset-token")
        auth_email = await session.scalar(
            select(TransactionalEmail).where(TransactionalEmail.kind == "AUTH_PASSWORD_RESET")
        )
        assert auth_email is not None
        _, _, body = service._decrypt(auth_email)
        assert "reset-password?token=phase11-reset-token" in body
        assert b"phase11-reset-token" not in auth_email.content_ciphertext
        await session.commit()


@pytest.mark.integration
async def test_analytics_validation_and_empty_dashboard_states_are_explicit() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        analytics = AnalyticsService(session)
        website_id = uuid4()
        with pytest.raises(AuthProblem, match="event type is invalid"):
            await analytics.record(
                website_id=website_id,
                event_type="UNKNOWN",
                idempotency_key="phase11-invalid-event-0001",
            )
        with pytest.raises(AuthProblem, match="event identifier"):
            await analytics.record(
                website_id=website_id,
                event_type="PAGE_VIEW",
                idempotency_key="short",
            )
        with pytest.raises(AuthProblem, match="page path"):
            await analytics.record(
                website_id=website_id,
                event_type="PAGE_VIEW",
                idempotency_key="phase11-invalid-path-0001",
                page_path="about",
            )
        with pytest.raises(AuthProblem, match="visitor value"):
            await analytics.record(
                website_id=website_id,
                event_type="PAGE_VIEW",
                idempotency_key="phase11-invalid-visitor-0001",
                visitor_hash=b"x",
            )
        with pytest.raises(AuthProblem, match="session value"):
            await analytics.record(
                website_id=website_id,
                event_type="PAGE_VIEW",
                idempotency_key="phase11-invalid-session-0001",
                session_hash=b"x",
            )
        with pytest.raises(AuthProblem, match="7, 30, or 90"):
            await analytics.dashboard(owner_user_id=uuid4(), timezone="UTC", period_days=14)
        with pytest.raises(AuthProblem, match="timezone is invalid"):
            await analytics.dashboard(
                owner_user_id=uuid4(), timezone="Not/A-Timezone", period_days=30
            )
        empty = await analytics.dashboard(owner_user_id=uuid4(), timezone="UTC", period_days=30)
        assert empty.has_published_website is False
        assert empty.has_meaningful_data is False
        assert empty.points == []
        with pytest.raises(ValueError, match="between 1 and 500"):
            await analytics.refresh_recent(0)


@pytest.mark.integration
async def test_transactional_email_terminal_and_invalid_paths_are_safe() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    crypto = AuthCrypto("phase11-terminal-email-secret-long-enough")
    async with factory() as session:
        service = TransactionalEmailService(session, crypto)
        with pytest.raises(AuthProblem, match="Email job not found"):
            await service.process_outbox_event(uuid4(), CapturingTransactionalProvider())
        unsupported = OutboxEvent(
            aggregate_type="TRANSACTIONAL_EMAIL",
            aggregate_id=uuid4(),
            event_type="transactional_email.unsupported",
            payload={},
            correlation_id="phase11-email-unsupported",
        )
        missing = OutboxEvent(
            aggregate_type="TRANSACTIONAL_EMAIL",
            aggregate_id=uuid4(),
            event_type="transactional_email.send_requested",
            payload={"transactional_email_id": str(uuid4())},
            correlation_id="phase11-email-missing",
        )
        session.add_all([unsupported, missing])
        await session.flush()
        assert (
            await service.process_outbox_event(unsupported.id, CapturingTransactionalProvider())
        ).last_error_code == "unsupported_transactional_email_event"
        assert (
            await service.process_outbox_event(missing.id, CapturingTransactionalProvider())
        ).last_error_code == "transactional_email_missing"
        key = f"phase11-terminal-email-{uuid4().hex}"
        purpose = f"transactional-email:{key}"
        failed_email = TransactionalEmail(
            resource_type="user",
            resource_id=None,
            kind="AUTH_VERIFICATION",
            recipient_ciphertext=crypto.encrypt(
                "owner@example.com", purpose=f"{purpose}:recipient"
            ),
            content_ciphertext=crypto.encrypt(
                '{"subject":"Verification","body":"Code"}', purpose=f"{purpose}:content"
            ),
            idempotency_key=key,
            state="FAILED",
            last_error_code="provider_permanent_failure",
        )
        session.add(failed_email)
        await session.flush()
        failed_event = OutboxEvent(
            aggregate_type="TRANSACTIONAL_EMAIL",
            aggregate_id=failed_email.id,
            event_type="transactional_email.send_requested",
            payload={"transactional_email_id": str(failed_email.id)},
            correlation_id="phase11-email-terminal",
        )
        session.add(failed_event)
        await session.flush()
        assert (
            await service.process_outbox_event(failed_event.id, CapturingTransactionalProvider())
        ).last_error_code == "provider_permanent_failure"
        invalid_payload = TransactionalEmail(
            resource_type="user",
            resource_id=None,
            kind="AUTH_VERIFICATION",
            recipient_ciphertext=crypto.encrypt(
                "owner@example.com", purpose=f"{purpose}:recipient"
            ),
            content_ciphertext=crypto.encrypt("[]", purpose=f"{purpose}:content"),
            idempotency_key=key,
            state="QUEUED",
        )
        with pytest.raises(ValueError, match="payload is invalid"):
            service._decrypt(invalid_payload)
        await session.rollback()


@pytest.mark.integration
async def test_first_visitor_and_first_lead_are_transactional_and_exactly_once() -> None:
    from zylora_api.db.activation_models import ProductEvent, WebsiteValueState
    from zylora_api.modules.analytics.activation import ProductAnalyticsService
    from zylora_api.modules.commerce.quotas import LeadService

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await published_site(session)
        product = ProductAnalyticsService(session)
        published_at = datetime.now(UTC)
        await product.mark_published(website, published_at)
        analytics = AnalyticsService(session)
        await analytics.record(
            website_id=website.id,
            owner_user_id=owner.id,
            event_type="PAGE_VIEW",
            idempotency_key=f"activation-page-{uuid4().hex}",
            session_hash=b"a" * 32,
        )
        first_state = await session.scalar(
            select(WebsiteValueState).where(WebsiteValueState.website_id == website.id)
        )
        assert first_state is not None and first_state.first_visitor_at is not None
        first_visitor_at = first_state.first_visitor_at
        await analytics.record(
            website_id=website.id,
            owner_user_id=owner.id,
            event_type="PAGE_VIEW",
            idempotency_key=f"activation-page-{uuid4().hex}",
            session_hash=b"b" * 32,
        )
        assert first_state.first_visitor_at == first_visitor_at

        key = f"activation-lead-{uuid4().hex}"
        first = await LeadService(session).capture(
            website_id=website.id,
            source="FORM",
            idempotency_key=key,
            name="Ada",
            email="ada@example.com",
            phone=None,
            enquiry="Please send details.",
            owner_country_code="ZZ",
            correlation_id="activation-first-lead",
            consent={"contact": True},
        )
        duplicate = await LeadService(session).capture(
            website_id=website.id,
            source="FORM",
            idempotency_key=key,
            name="Ada",
            email="ada@example.com",
            phone=None,
            enquiry="Please send details.",
            owner_country_code="ZZ",
            correlation_id="activation-first-lead-duplicate",
            consent={"contact": True},
        )
        assert duplicate.duplicate is True
        assert duplicate.lead.id == first.lead.id
        assert (
            await session.scalar(
                select(func.count(ProductEvent.id)).where(
                    ProductEvent.website_id == website.id,
                    ProductEvent.event_type == "FIRST_VISITOR",
                )
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count(ProductEvent.id)).where(
                    ProductEvent.website_id == website.id,
                    ProductEvent.event_type == "FIRST_LEAD",
                )
            )
            == 1
        )
        assert first_state.first_lead_at is not None
        await session.commit()


@pytest.mark.integration
async def test_attribution_digest_zero_lead_and_north_star_are_idempotent_and_isolated() -> None:
    from datetime import timedelta

    from zylora_api.db.activation_models import (
        AcquisitionAttribution,
        WebsiteDigestDelivery,
        WebsiteValueState,
        ZeroLeadCheckpoint,
    )
    from zylora_api.modules.analytics.activation import AttributionInput, ProductAnalyticsService

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await published_site(session)
        service = ProductAnalyticsService(session)
        await service.capture_attribution(
            user_id=owner.id,
            attribution=AttributionInput(
                utm_source="instagram",
                utm_campaign="launch",
                landing_page="/signup?utm_source=instagram",
            ),
            country_code="in",
            signup_source="EMAIL",
        )
        await service.capture_attribution(
            user_id=owner.id,
            attribution=AttributionInput(utm_source="other"),
            country_code="US",
            signup_source="EMAIL",
        )
        attribution = await session.scalar(
            select(AcquisitionAttribution).where(AcquisitionAttribution.user_id == owner.id)
        )
        assert attribution is not None
        assert attribution.normalized_source == "INSTAGRAM"
        assert attribution.country_code == "IN"
        assert attribution.utm_campaign == "launch"

        published_at = datetime.now(UTC) - timedelta(days=31)
        await service.mark_published(website, published_at)
        queued = await service.queue_monthly_digests(
            AuthCrypto("activation-digest-secret-long-enough"), limit=100
        )
        assert queued >= 1
        assert (
            await service.queue_monthly_digests(
                AuthCrypto("activation-digest-secret-long-enough"), limit=100
            )
            == 0
        )
        assert (
            await session.scalar(
                select(func.count(WebsiteDigestDelivery.id)).where(
                    WebsiteDigestDelivery.website_id == website.id
                )
            )
            == 1
        )
        assert await service.process_zero_lead_checkpoints(limit=100) >= 2
        assert await service.process_zero_lead_checkpoints(limit=100) == 0
        assert (
            await session.scalar(
                select(func.count(ZeroLeadCheckpoint.id)).where(
                    ZeroLeadCheckpoint.website_id == website.id
                )
            )
            == 2
        )
        state = await session.scalar(
            select(WebsiteValueState).where(WebsiteValueState.website_id == website.id)
        )
        assert state is not None and state.first_lead_at is None
        growth = await service.admin_growth(30)
        assert growth.active_value_sites_30d >= 0
        assert [item.days for item in growth.retention] == [30, 60, 90]
        await session.commit()
