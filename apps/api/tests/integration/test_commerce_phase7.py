from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zylora_api.db.auth_models import User
from zylora_api.db.commerce_models import Invoice, PaymentEvent, Subscription
from zylora_api.db.lead_models import Lead
from zylora_api.db.session import get_engine
from zylora_api.db.website_models import WebsiteOwnership
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.commerce.ownership import OwnershipService
from zylora_api.modules.commerce.payments import PaymentService, VerifiedSubscriptionPayment
from zylora_api.modules.commerce.publishing import PublishEligibilityService, PublishService
from zylora_api.modules.commerce.quotas import LeadService
from zylora_api.modules.commerce.service import CatalogService, SubscriptionService
from zylora_api.modules.editor.revisions import AiCreditService
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.websites.service import WebsiteService


def template_document(page_count: int) -> dict[str, object]:
    pages: list[dict[str, object]] = []
    for index in range(page_count):
        label = "Home" if index == 0 else f"Page {index}"
        pages.append(
            {
                "id": f"phase7-page-{index}",
                "slug": "home" if index == 0 else f"page-{index}",
                "label": label,
                "parent_page_id": None,
                "sort_order": index,
                "is_home": index == 0,
                "show_in_navigation": index < 8,
                "status": "ACTIVE",
                "seo": {"title": label, "description": f"Information about {label}."},
                "components": [
                    {
                        "id": f"hero-{index}",
                        "type": "HERO",
                        "props": {"heading": label, "body": f"Welcome to {label}."},
                        "children": [],
                        "responsive": {},
                        "interactions": [],
                    }
                ],
            }
        )
    return {
        "schema_version": "1.0.0",
        "registry_version": "1.0.0",
        "metadata": {
            "name": "Phase 7 Commerce Template",
            "description": "Plan and publication eligibility fixture.",
            "language": "en",
        },
        "theme": {
            "primary": "#315C4A",
            "accent": "#D77A45",
            "surface": "#FFFFFF",
            "ink": "#17201E",
            "heading_font": "MANROPE",
            "body_font": "INTER",
        },
        "assets": [],
        "pages": pages,
        "features": [],
        "requirements": [],
        "provenance": "CURATED",
    }


async def make_site(
    session: AsyncSession,
    page_count: int,
    *,
    country_code: str = "ZZ",
    owner: User | None = None,
) -> tuple[User, object]:
    unique = uuid4().hex
    if owner is None:
        owner = User(
            account_type="USER",
            normalized_email=f"phase7-owner-{unique}@example.com",
            display_email=f"phase7-owner-{unique}@example.com",
            status="ACTIVE",
            verified_at=datetime.now(UTC),
            billing_country_code=country_code,
        )
        session.add(owner)
        await session.flush()
    service = TemplateService(session, AuthCrypto("phase7-commerce-test-secret-long-enough"))
    template = await service.create(
        TemplateCreateRequest(
            slug=f"phase7-{unique}",
            name="Phase 7 Commerce",
            summary="Commerce and publication fixture.",
            category_slug=f"phase7-category-{unique}",
            category_name="Commerce",
            category_description="Commerce integration fixtures.",
            tags=[f"phase7-tag-{unique}"],
            featured_order=100,
        ),
        owner.id,
    )
    await service.add_version(template.id, template_document(page_count), owner.id)
    assert (await service.validate(template.id, 1, owner.id)).status == "VALIDATED"
    await service.approve(template.id, 1)
    await service.publish(template.id, 1)
    website = await WebsiteService(session).instantiate(template.slug, owner.id)
    await session.flush()
    return owner, website


async def activate_plan(session: AsyncSession, user: User, code: str, marker: str) -> Subscription:
    bundles = await CatalogService(session).current(user.billing_country_code)
    bundle = next(item for item in bundles if item.plan.code == code)
    payment = await SubscriptionService(session).create_payment(
        user.id,
        user.billing_country_code,
        bundle.plan.id,
        f"payment-{marker}-{uuid4().hex}",
    )
    now = datetime.now(UTC)
    return await PaymentService(session).process_subscription_payment(
        VerifiedSubscriptionPayment(
            provider="TEST",
            provider_event_id=f"event-{marker}-{uuid4().hex}",
            provider_payment_reference=f"provider-{marker}-{uuid4().hex}",
            payment_id=payment.id,
            amount_minor=payment.expected_amount_minor,
            currency=payment.expected_currency,
            period_start=now,
            period_end=now + timedelta(days=30),
            raw_body_hash=uuid4().hex + uuid4().hex,
            evidence={"verified": 1},
        )
    )


@pytest.mark.integration
async def test_permanent_regional_catalog_and_entitlements() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        india = await CatalogService(session).response("IN")
        world = await CatalogService(session).response("US")
        assert [item.code for item in india.items] == ["FREE", "BASIC", "GROWTH", "BUSINESS"]
        assert [item.price.amount_minor for item in india.items] == [0, 39900, 99900, 199900]
        assert [item.price.amount_minor for item in world.items] == [0, 900, 1900, 3900]
        assert india.currency == "INR" and world.currency == "USD"
        assert india.items[2].most_popular and world.items[2].most_popular
        assert all(item.interval == "MONTHLY" for item in india.items + world.items)
        expected = {
            "FREE": (1, False, False, 15, 0, "BASIC", "AUTOMATIC_BASIC"),
            "BASIC": (5, True, True, 100, 150, "STANDARD", "FULL_STANDARD"),
            "GROWTH": (20, True, True, 500, 750, "ADVANCED", "ADVANCED_AI"),
            "BUSINESS": (
                "UNLIMITED",
                True,
                True,
                1500,
                2000,
                "ADVANCED_REPORTING",
                "ADVANCED_MONITORING",
            ),
        }
        for plan in india.items:
            ent = plan.entitlements
            assert (
                ent["max_pages"],
                ent["custom_domain"],
                ent["remove_branding"],
                ent["ai_monthly_credits"],
                ent["whatsapp_monthly_notifications"],
                ent["analytics_tier"],
                ent["seo_tier"],
            ) == expected[plan.code]
            assert ent["lead_capture_unlimited"] is True
        await session.rollback()


@pytest.mark.integration
async def test_publish_limits_existing_plan_reuse_and_one_live_reservation() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, one_page = await make_site(session, 1)
        _, five_pages = await make_site(session, 5)
        _, thirty_pages = await make_site(session, 30, owner=owner)
        free = await PublishEligibilityService(session).evaluate(
            one_page.id, owner.id, owner.billing_country_code, "ZYLORA_SUBDOMAIN"
        )
        assert free.status == "ELIGIBLE" and free.recommended_plan_code == "FREE"
        assert one_page.status == "DRAFT"
        basic = await PublishEligibilityService(session).evaluate(
            five_pages.id,
            five_pages.owner_user_id,
            "ZZ",
            "CUSTOM",
        )
        assert basic.status == "UPGRADE_REQUIRED"
        assert not basic.plans[0].eligible and basic.plans[1].eligible
        large = await PublishEligibilityService(session).evaluate(
            thirty_pages.id, owner.id, owner.billing_country_code, "ZYLORA_SUBDOMAIN"
        )
        assert large.status == "UPGRADE_REQUIRED"
        assert [item.eligible for item in large.plans] == [False, False, False, True]
        assert len(await WebsiteService(session).pages(thirty_pages.id)) == 30
        await activate_plan(session, owner, "BUSINESS", "business-reuse")
        reusable = await PublishEligibilityService(session).evaluate(
            thirty_pages.id, owner.id, owner.billing_country_code, "CUSTOM"
        )
        assert reusable.status == "ELIGIBLE" and reusable.reuse_existing_subscription
        result = await PublishService(session).request_publish(
            thirty_pages.id,
            owner.id,
            owner.billing_country_code,
            "CUSTOM",
            "publish-business-0001",
            "phase7-publish",
        )
        assert result.status == "PUBLISHING" and result.plan_code == "BUSINESS"
        blocked = await PublishEligibilityService(session).evaluate(
            one_page.id, owner.id, owner.billing_country_code, "ZYLORA_SUBDOMAIN"
        )
        assert blocked.status == "INELIGIBLE"
        assert all(not item.eligible for item in blocked.plans)
        cancelled = await PublishService(session).request_unpublish(
            thirty_pages.id, owner.id, "phase7-cancel"
        )
        assert cancelled.status == "DRAFT"
        second = await PublishService(session).request_publish(
            one_page.id,
            owner.id,
            owner.billing_country_code,
            "ZYLORA_SUBDOMAIN",
            "publish-business-0002",
            "phase7-second",
        )
        assert second.status == "PUBLISHING"
        await session.rollback()


@pytest.mark.integration
async def test_payment_snapshot_webhook_idempotency_ai_allowance_and_downgrade_safety() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        user, website = await make_site(session, 30, country_code="IN")
        bundles = await CatalogService(session).current("IN")
        business = next(item for item in bundles if item.plan.code == "BUSINESS")
        payment = await SubscriptionService(session).create_payment(
            user.id, "IN", business.plan.id, "payment-idempotency-0001"
        )
        assert payment.expected_amount_minor == 199900 and payment.expected_currency == "INR"
        now = datetime.now(UTC)
        verified = VerifiedSubscriptionPayment(
            provider="TEST",
            provider_event_id=f"event-{uuid4().hex}",
            provider_payment_reference=f"provider-{uuid4().hex}",
            payment_id=payment.id,
            amount_minor=199900,
            currency="INR",
            period_start=now,
            period_end=now + timedelta(days=30),
            raw_body_hash=uuid4().hex + uuid4().hex,
            evidence={"verified": 1},
        )
        first = await PaymentService(session).process_subscription_payment(verified)
        duplicate = await PaymentService(session).process_subscription_payment(verified)
        assert duplicate.id == first.id
        assert await session.scalar(select(func.count(PaymentEvent.id))) == 1
        assert (
            await session.scalar(
                select(func.count(Invoice.id)).where(Invoice.payment_id == payment.id)
            )
            == 1
        )
        account = await AiCreditService(session).account(user.id, lock=True)
        assert account.allowance == 1500 and account.balance == 1500
        pages_before = len(await WebsiteService(session).pages(website.id))
        await activate_plan(session, user, "BASIC", "downgrade")
        assert len(await WebsiteService(session).pages(website.id)) == pages_before == 30
        downgraded = await PublishEligibilityService(session).evaluate(
            website.id, user.id, "IN", "ZYLORA_SUBDOMAIN"
        )
        assert downgraded.status == "UPGRADE_REQUIRED"
        assert [item.plan.code for item in downgraded.plans if item.eligible] == ["BUSINESS"]
        account = await AiCreditService(session).account(user.id, lock=True)
        assert account.allowance == 100 and account.balance == 100
        await session.rollback()


@pytest.mark.integration
async def test_unlimited_leads_whatsapp_quota_and_atomic_owner_transfer() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await make_site(session, 1)
        recipient = User(
            account_type="USER",
            normalized_email=f"recipient-{uuid4().hex}@example.com",
            display_email=f"recipient-{uuid4().hex}@example.com",
            status="ACTIVE",
            verified_at=datetime.now(UTC),
            billing_country_code="ZZ",
        )
        session.add(recipient)
        await session.flush()
        transfer = await OwnershipService(session).transfer(
            website.id,
            owner.id,
            recipient.normalized_email,
            "ownership-transfer-0001",
        )
        assert transfer.status == "COMPLETED" and website.owner_user_id == recipient.id
        open_owners = await session.scalar(
            select(func.count(WebsiteOwnership.id)).where(
                WebsiteOwnership.website_id == website.id,
                WebsiteOwnership.ended_at.is_(None),
            )
        )
        assert open_owners == 1
        with pytest.raises(AuthProblem):
            await WebsiteService(session).get_for_owner(website.id, owner.id)
        await activate_plan(session, recipient, "BASIC", "whatsapp-basic")
        website.status = "PUBLISHED"
        website.live_owner_user_id = recipient.id
        website.published_version_id = website.current_version_id
        website.publication_domain_type = "ZYLORA_SUBDOMAIN"
        await session.flush()
        lead_service = LeadService(session)
        last = None
        for index in range(151):
            last = await lead_service.capture(
                website_id=website.id,
                source="FORM",
                idempotency_key=f"lead-{index:04d}",
                name=f"Lead {index}",
                email=f"lead-{index}@example.com",
                phone=None,
                enquiry="Please contact me.",
                owner_country_code="ZZ",
                correlation_id=f"lead-{index}",
            )
        assert last is not None and not last.lead.whatsapp_notification_queued
        assert (
            await session.scalar(select(func.count(Lead.id)).where(Lead.website_id == website.id))
            == 151
        )
        duplicate = await lead_service.capture(
            website_id=website.id,
            source="FORM",
            idempotency_key="lead-0150",
            name="Lead 150",
            email="lead-150@example.com",
            phone=None,
            enquiry="Please contact me.",
            owner_country_code="ZZ",
            correlation_id="duplicate",
        )
        assert duplicate.duplicate
        assert (
            await session.scalar(select(func.count(Lead.id)).where(Lead.website_id == website.id))
            == 151
        )
        await session.rollback()
