from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zylora_api.db.auth_models import User
from zylora_api.db.commerce_models import Invoice, PaymentEvent, Subscription
from zylora_api.db.deployment_models import Deployment, Domain
from zylora_api.db.lead_models import Lead
from zylora_api.db.models import OutboxEvent
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
from zylora_api.modules.publishing.artifacts import ArtifactBuilder
from zylora_api.modules.publishing.providers import (
    DomainProviderError,
    MemoryDomainProvider,
    ProviderDomain,
)
from zylora_api.modules.publishing.service import DeploymentService, DomainService
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.websites.service import WebsiteService
from zylora_api.storage.memory import MemoryObjectStorage


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
async def test_deployment_activation_failure_preserves_the_current_live_site() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await make_site(session, 1)
        request = await PublishService(session).request_publish(
            website.id,
            owner.id,
            owner.billing_country_code,
            "ZYLORA_SUBDOMAIN",
            "phase8-publish-activation-0001",
            "phase8-activation",
        )
        deployment = await session.get(Deployment, request.deployment_id)
        domain = await session.get(Domain, request.domain_id)
        assert deployment is not None and domain is not None
        provider = MemoryDomainProvider()
        provider.healthy.add((domain.hostname, deployment.id))
        activated = await DeploymentService(session).process_publish(
            deployment.id,
            provider,
            ArtifactBuilder(MemoryObjectStorage()),
            "phase8-activation",
        )
        assert activated.state == "ACTIVE"
        assert website.status == "PUBLISHED" and website.active_deployment_id == deployment.id
        assert domain.is_active and domain.state == "ACTIVE"

        rollback = await DeploymentService(session).queue_rollback(
            website.id,
            owner.id,
            deployment.id,
            "phase8-rollback-failure-0001",
            "phase8-rollback",
        )
        failed = await DeploymentService(session).process_publish(
            rollback.id,
            provider,
            ArtifactBuilder(MemoryObjectStorage()),
            "phase8-rollback",
        )
        assert failed.state == "FAILED"
        assert website.status == "PUBLISHED" and website.active_deployment_id == deployment.id
        assert domain.is_active and domain.state == "ACTIVE"
        await session.rollback()


@pytest.mark.integration
async def test_verified_custom_domain_activates_only_after_server_side_dns_check() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await make_site(session, 1)
        await activate_plan(session, owner, "BASIC", "phase8-custom-domain")
        provider = MemoryDomainProvider()
        domain = await DomainService(session).create_custom(
            website.id,
            owner.id,
            "www.phase8-example.test",
            "phase8-custom-domain-request-0001",
            provider,
        )
        assert domain.state == "PENDING_DNS" and domain.verification_record_value
        provider.mark_custom_active(domain.hostname)
        verified = await DomainService(session).verify_custom(domain.id, owner.id, provider)
        assert verified.state == "VERIFIED" and verified.tls_status == "ACTIVE"
        request = await PublishService(session).request_publish(
            website.id,
            owner.id,
            owner.billing_country_code,
            "CUSTOM",
            "phase8-custom-domain-publish-0001",
            "phase8-custom-domain",
            hostname=domain.hostname,
        )
        deployment = await session.get(Deployment, request.deployment_id)
        event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == deployment.id)
        )
        assert deployment is not None and event is not None
        provider.healthy.add((domain.hostname, deployment.id))
        processed = await DeploymentService(session).process_outbox_event(
            event.id,
            provider,
            ArtifactBuilder(MemoryObjectStorage()),
        )
        assert processed.state == "PUBLISHED" and deployment.state == "ACTIVE"
        assert website.status == "PUBLISHED" and domain.is_active
        await PublishService(session).request_unpublish(website.id, owner.id, "phase8-unpublish")
        unpublish_event = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == website.id,
                OutboxEvent.event_type == "website.unpublish_requested",
            )
        )
        assert unpublish_event is not None
        completed = await DeploymentService(session).process_outbox_event(
            unpublish_event.id,
            provider,
            ArtifactBuilder(MemoryObjectStorage()),
        )
        assert completed.state == "PUBLISHED" and website.status == "UNPUBLISHED"
        await session.rollback()


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
            "FREE": (2, False, False, 15, 0, "BASIC", "AUTOMATIC_BASIC"),
            "BASIC": (5, True, True, 100, 150, "STANDARD", "FULL_STANDARD"),
            "GROWTH": (8, True, True, 500, 750, "ADVANCED", "ADVANCED_AI"),
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
            "ZYLORA_SUBDOMAIN",
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


@pytest.mark.integration
async def test_domain_service_preserves_owner_entitlements_idempotency_and_verification_state() -> (
    None
):
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await make_site(session, 1)
        service = DomainService(session)
        provider = MemoryDomainProvider()

        with pytest.raises(AuthProblem, match="does not include custom domains"):
            await service.create_custom(
                website.id,
                owner.id,
                "www.entitlement.example",
                "phase8-domain-entitlement-0001",
                provider,
            )
        await activate_plan(session, owner, "BASIC", "phase8-domain-entitlement")

        class UnavailableCreateProvider:
            async def create_custom(self, _: str, __: str) -> ProviderDomain:
                raise DomainProviderError(
                    "cloudflare_unavailable", "Cloudflare could not be reached."
                )

        with pytest.raises(AuthProblem, match="Cloudflare could not be reached"):
            await service.create_custom(
                website.id,
                owner.id,
                "www.unavailable.example",
                "phase8-domain-provider-failure-0001",
                UnavailableCreateProvider(),  # type: ignore[arg-type]
            )

        created = await service.create_custom(
            website.id,
            owner.id,
            "WWW.Example.TEST",
            "phase8-domain-idempotency-0001",
            provider,
        )
        duplicate = await service.create_custom(
            website.id,
            owner.id,
            "www.example.test",
            "phase8-domain-idempotency-0002",
            provider,
        )
        assert duplicate.id == created.id and duplicate.hostname == "www.example.test"

        with pytest.raises(AuthProblem, match="Custom domain not found"):
            await service.verify_custom(uuid4(), owner.id, provider)
        created.provider_hostname_id = None
        with pytest.raises(AuthProblem, match="verification is not ready"):
            await service.verify_custom(created.id, owner.id, provider)

        class UnavailableInspectProvider:
            async def inspect(self, *_: object) -> ProviderDomain:
                raise DomainProviderError(
                    "cloudflare_unavailable", "Cloudflare could not be reached."
                )

        created.provider_hostname_id = "custom-provider-id"
        with pytest.raises(AuthProblem, match="Cloudflare could not be reached"):
            await service.verify_custom(created.id, owner.id, UnavailableInspectProvider())  # type: ignore[arg-type]

        class FailedVerificationProvider:
            async def inspect(self, *_: object) -> ProviderDomain:
                return ProviderDomain("custom-provider-id", "FAILED", "FAILED")

        failed = await service.verify_custom(
            created.id,
            owner.id,
            FailedVerificationProvider(),  # type: ignore[arg-type]
        )
        assert failed.state == "VERIFICATION_FAILED"
        assert failed.failure_code == "cloudflare_verification_failed"

        with pytest.raises(AuthProblem, match="Enter a verified custom domain"):
            await service.reserve_for_publish(website, "CUSTOM", None)
        with pytest.raises(AuthProblem, match="Verify the custom domain"):
            await service.reserve_for_publish(website, "CUSTOM", created.hostname)
        with pytest.raises(AuthProblem, match="assigned safely"):
            await service.reserve_for_publish(website, "ZYLORA_SUBDOMAIN", "unsafe.example.test")
        reserved = await service.reserve_for_publish(website, "ZYLORA_SUBDOMAIN", None)
        assert (
            await service.reserve_for_publish(website, "ZYLORA_SUBDOMAIN", None)
        ).id == reserved.id
        await session.rollback()


@pytest.mark.integration
async def test_deployment_state_machine_handles_supersession_and_outbox_terminal_cases() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await make_site(session, 1)
        request = await PublishService(session).request_publish(
            website.id,
            owner.id,
            owner.billing_country_code,
            "ZYLORA_SUBDOMAIN",
            "phase8-state-machine-publish-0001",
            "phase8-state-machine",
        )
        first = await session.get(Deployment, request.deployment_id)
        domain = await session.get(Domain, request.domain_id)
        assert first is not None and domain is not None
        assert (
            await DeploymentService(session).queue_publish(
                website,
                "ZYLORA_SUBDOMAIN",
                None,
                "phase8-state-machine-publish-0001",
                "phase8-state-machine",
            )
        ).id == first.id
        provider = MemoryDomainProvider()
        provider.healthy.add((domain.hostname, first.id))
        artifacts = ArtifactBuilder(MemoryObjectStorage())
        assert (
            await DeploymentService(session).process_publish(first.id, provider, artifacts, "first")
        ).state == "ACTIVE"
        assert (
            await DeploymentService(session).process_publish(
                first.id, provider, artifacts, "duplicate"
            )
        ) is first

        replacement = await DeploymentService(session).queue_rollback(
            website.id,
            owner.id,
            first.id,
            "phase8-state-machine-rollback-0001",
            "phase8-state-machine",
        )
        provider.healthy.add((domain.hostname, replacement.id))
        activated = await DeploymentService(session).process_publish(
            replacement.id, provider, artifacts, "replacement"
        )
        assert activated.state == "ACTIVE" and first.state == "SUPERSEDED"
        assert website.active_deployment_id == replacement.id
        assert (
            await DeploymentService(session).cancel_pending_publish(website, "cancel-none") is None
        )
        with pytest.raises(AuthProblem, match="cannot be restored"):
            await DeploymentService(session).queue_rollback(
                website.id,
                owner.id,
                uuid4(),
                "phase8-missing-rollback-target-0001",
                "phase8-state-machine",
            )
        with pytest.raises(AuthProblem, match="Publication event not found"):
            await DeploymentService(session).process_outbox_event(uuid4(), provider, artifacts)

        delivered = OutboxEvent(
            aggregate_type="DEPLOYMENT",
            aggregate_id=replacement.id,
            event_type="deployment.publish_requested",
            payload={"deployment_id": str(replacement.id)},
            correlation_id="phase8-already-delivered",
            state="PUBLISHED",
        )
        unsupported = OutboxEvent(
            aggregate_type="DEPLOYMENT",
            aggregate_id=replacement.id,
            event_type="deployment.unknown",
            payload={},
            correlation_id="phase8-unsupported-event",
        )
        session.add_all((delivered, unsupported))
        await session.flush()
        assert (
            await DeploymentService(session).process_outbox_event(delivered.id, provider, artifacts)
            is delivered
        )
        completed = await DeploymentService(session).process_outbox_event(
            unsupported.id, provider, artifacts
        )
        assert completed.state == "FAILED"
        assert completed.last_error_code == "publication_processing_failed"

        await PublishService(session).request_unpublish(
            website.id, owner.id, "phase8-unpublish-failure"
        )
        unpublish_event = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == website.id,
                OutboxEvent.event_type == "website.unpublish_requested",
            )
        )
        assert unpublish_event is not None

        class FailingDeactivateProvider:
            async def deactivate(self, _: str, __: str) -> None:
                raise DomainProviderError(
                    "cloudflare_unavailable", "Cloudflare could not be reached."
                )

        failed_event = await DeploymentService(session).process_outbox_event(
            unpublish_event.id,
            FailingDeactivateProvider(),  # type: ignore[arg-type]
            artifacts,
        )
        assert failed_event.state == "FAILED"
        assert failed_event.last_error_code == "cloudflare_unavailable"
        assert website.status == "PUBLISHED" and domain.state == "ACTIVE" and domain.is_active
        await session.rollback()


@pytest.mark.integration
async def test_worker_claims_only_ready_publication_events_with_a_durable_lease() -> None:
    """The dispatcher lease is database-backed so retries cannot double-dispatch a publication."""

    from sqlalchemy import delete
    from zylora_worker import tasks

    marker = f"phase8-worker-claim-{uuid4().hex}"
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    event_ids: set[str] = set()
    try:
        async with factory() as session:
            events = [
                OutboxEvent(
                    aggregate_type="DEPLOYMENT",
                    aggregate_id=uuid4(),
                    event_type="deployment.publish_requested",
                    payload={"deployment_id": str(uuid4())},
                    correlation_id=marker,
                ),
                OutboxEvent(
                    aggregate_type="DEPLOYMENT",
                    aggregate_id=uuid4(),
                    event_type="deployment.rollback_requested",
                    payload={"deployment_id": str(uuid4())},
                    correlation_id=marker,
                ),
            ]
            session.add_all(events)
            await session.commit()
            event_ids = {str(event.id) for event in events}

        claimed = set(await tasks._claim_publication_events(100))
        assert event_ids.issubset(claimed)

        async with factory() as session:
            leased = list(
                (
                    await session.scalars(
                        select(OutboxEvent).where(OutboxEvent.correlation_id == marker)
                    )
                ).all()
            )
            assert len(leased) == 2
            assert all(event.lease_owner and event.leased_until for event in leased)
    finally:
        async with factory() as session:
            await session.execute(delete(OutboxEvent).where(OutboxEvent.correlation_id == marker))
            await session.commit()


@pytest.mark.integration
async def test_deployment_service_rejects_invalid_queues_and_keeps_first_failure_offline() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await make_site(session, 1)
        service = DeploymentService(session)
        assert await DomainService(session).list_for_owner(website.id, owner.id) == []
        assert await service.cancel_pending_publish(website, "no-pending-deployment") is None
        with pytest.raises(AuthProblem, match="live Website deployment is required"):
            await service.queue_rollback(
                website.id,
                owner.id,
                uuid4(),
                "phase8-draft-rollback-0001",
                "phase8-invalid-queue",
            )
        website.current_version_id = None
        with pytest.raises(AuthProblem, match="no valid revision"):
            await service.queue_publish(
                website,
                "ZYLORA_SUBDOMAIN",
                None,
                "phase8-no-revision-0001",
                "phase8-invalid-queue",
            )
        with pytest.raises(AuthProblem, match="Deployment not found"):
            await service.process_publish(
                uuid4(),
                MemoryDomainProvider(),
                ArtifactBuilder(MemoryObjectStorage()),
                "phase8-missing-deployment",
            )
        await session.rollback()


@pytest.mark.integration
async def test_first_deployment_failure_never_sets_a_live_website_pointer() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await make_site(session, 1)
        request = await PublishService(session).request_publish(
            website.id,
            owner.id,
            owner.billing_country_code,
            "ZYLORA_SUBDOMAIN",
            "phase8-first-failure-publish-0001",
            "phase8-first-failure",
        )
        deployment = await session.get(Deployment, request.deployment_id)
        domain = await session.get(Domain, request.domain_id)
        assert deployment is not None and domain is not None

        failed = await DeploymentService(session).process_publish(
            deployment.id,
            MemoryDomainProvider(),
            ArtifactBuilder(MemoryObjectStorage()),
            "phase8-first-failure",
        )
        assert failed.state == "FAILED"
        assert failed.failure_code == "deployment_health_check_failed"
        assert website.status == "FAILED" and website.active_deployment_id is None
        assert website.live_owner_user_id is None and website.publication_domain_type is None
        assert domain.state == "PROVISIONING_FAILED" and not domain.is_active
        await session.rollback()
