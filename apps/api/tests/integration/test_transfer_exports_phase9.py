from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zylora_api.db.auth_models import User
from zylora_api.db.commerce_models import ExportPurchase, PaymentEvent
from zylora_api.db.deployment_models import Deployment, Domain
from zylora_api.db.models import OutboxEvent
from zylora_api.db.session import get_engine
from zylora_api.db.website_models import WebsiteOwnership
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.commerce.exports import ExportPriceService, ExportService
from zylora_api.modules.commerce.ownership import (
    TRANSFER_CONFIRMATION_VERSION,
    OwnershipService,
)
from zylora_api.modules.commerce.payments import PaymentService, VerifiedExportPayment
from zylora_api.modules.commerce.publishing import PublishService
from zylora_api.modules.publishing.artifacts import ArtifactBuilder
from zylora_api.modules.publishing.providers import MemoryDomainProvider
from zylora_api.modules.publishing.service import DeploymentService
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.websites.service import WebsiteService
from zylora_api.storage.memory import MemoryObjectStorage


def document() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "registry_version": "1.0.0",
        "metadata": {
            "name": "Phase 9 export fixture",
            "description": "A static export source.",
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
        "pages": [
            {
                "id": "phase9-home",
                "slug": "home",
                "label": "Home",
                "parent_page_id": None,
                "sort_order": 0,
                "is_home": True,
                "show_in_navigation": True,
                "status": "ACTIVE",
                "seo": {"title": "Export home", "description": "Static Website content."},
                "components": [
                    {
                        "id": "phase9-hero",
                        "type": "HERO",
                        "props": {"heading": "Export-ready", "body": "A safe Website export."},
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


async def create_user(session: AsyncSession, prefix: str) -> User:
    unique = uuid4().hex
    user = User(
        account_type="USER",
        normalized_email=f"{prefix}-{unique}@example.com",
        display_email=f"{prefix}-{unique}@example.com",
        status="ACTIVE",
        verified_at=datetime.now(UTC),
        billing_country_code="ZZ",
    )
    session.add(user)
    await session.flush()
    return user


async def make_site(session: AsyncSession, owner: User) -> object:
    unique = uuid4().hex
    templates = TemplateService(session, AuthCrypto("phase9-test-secret-long-enough-for-auth"))
    template = await templates.create(
        TemplateCreateRequest(
            slug=f"phase9-{unique}",
            name="Phase 9 Website",
            summary="Transfer and export fixture.",
            category_slug=f"phase9-category-{unique}",
            category_name="Phase 9",
            category_description="Phase 9 integration test category.",
            tags=[f"phase9-{unique}"],
            featured_order=1,
        ),
        owner.id,
    )
    await templates.add_version(template.id, document(), owner.id)
    assert (await templates.validate(template.id, 1, owner.id)).status == "VALIDATED"
    await templates.approve(template.id, 1)
    await templates.publish(template.id, 1)
    return await WebsiteService(session).instantiate(template.slug, owner.id)


async def configure_usd_export_price(session: AsyncSession, admin: User) -> None:
    await ExportPriceService(session).configure(
        currency="USD",
        amount_minor=1900,
        active=True,
        configured_by_user_id=admin.id,
    )


@pytest.mark.integration
async def test_offline_transfer_is_atomic_and_removes_the_stale_owner() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "phase9-owner")
        recipient = await create_user(session, "phase9-recipient")
        website = await make_site(session, owner)
        service = OwnershipService(session)
        validated_website, validated_recipient = await service.validate_recipient(
            website.id, owner.id, recipient.normalized_email
        )
        assert validated_website.id == website.id and validated_recipient.id == recipient.id
        transfer = await service.start_transfer(
            website.id,
            owner.id,
            recipient.normalized_email,
            TRANSFER_CONFIRMATION_VERSION,
            "phase9-offline-transfer-0001",
            "phase9-offline-transfer",
        )
        assert transfer.status == "COMPLETED" and website.owner_user_id == recipient.id
        assert transfer.confirmation_version == TRANSFER_CONFIRMATION_VERSION
        assert (
            await session.scalar(
                select(func.count(WebsiteOwnership.id)).where(
                    WebsiteOwnership.website_id == website.id,
                    WebsiteOwnership.ended_at.is_(None),
                )
            )
            == 1
        )
        with pytest.raises(AuthProblem):
            await WebsiteService(session).get_for_owner(website.id, owner.id)
        assert (
            await WebsiteService(session).get_for_owner(website.id, recipient.id)
        ).id == website.id
        with pytest.raises(AuthProblem, match="self"):
            await service.validate_recipient(website.id, recipient.id, recipient.normalized_email)
        await session.rollback()


@pytest.mark.integration
async def test_live_transfer_waits_for_route_deactivation_then_changes_owner() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "phase9-live-owner")
        recipient = await create_user(session, "phase9-live-recipient")
        website = await make_site(session, owner)
        publish = await PublishService(session).request_publish(
            website.id,
            owner.id,
            owner.billing_country_code,
            "ZYLORA_SUBDOMAIN",
            "phase9-live-publish-0001",
            "phase9-live-publish",
        )
        deployment = await session.get(Deployment, publish.deployment_id)
        domain = await session.get(Domain, publish.domain_id)
        assert deployment is not None and domain is not None
        provider = MemoryDomainProvider()
        provider.healthy.add((domain.hostname, deployment.id))
        await DeploymentService(session).process_publish(
            deployment.id, provider, ArtifactBuilder(MemoryObjectStorage()), "phase9-live-publish"
        )
        transfer = await OwnershipService(session).start_transfer(
            website.id,
            owner.id,
            recipient.normalized_email,
            TRANSFER_CONFIRMATION_VERSION,
            "phase9-live-transfer-0001",
            "phase9-live-transfer",
        )
        assert transfer.status == "DEACTIVATING" and website.status == "UNPUBLISHING"
        with pytest.raises(AuthProblem, match="in progress"):
            await OwnershipService(session).start_transfer(
                website.id,
                owner.id,
                recipient.normalized_email,
                TRANSFER_CONFIRMATION_VERSION,
                "phase9-live-transfer-concurrent-0001",
                "phase9-live-transfer",
            )
        event = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == website.id,
                OutboxEvent.event_type == "website.unpublish_requested",
                OutboxEvent.payload["transfer_id"].astext == str(transfer.id),
            )
        )
        assert event is not None
        completed_event = await DeploymentService(session).process_outbox_event(
            event.id, provider, ArtifactBuilder(MemoryObjectStorage())
        )
        assert completed_event.state == "PUBLISHED"
        assert transfer.status == "COMPLETED" and website.owner_user_id == recipient.id
        assert website.status == "DRAFT" and website.live_owner_user_id is None
        assert not domain.is_active and domain.state == "INACTIVE"
        with pytest.raises(AuthProblem):
            await WebsiteService(session).get_for_owner(website.id, owner.id)
        await session.rollback()


@pytest.mark.integration
async def test_paid_export_snapshots_price_and_generates_a_private_static_zip() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "phase9-export-owner")
        admin = await create_user(session, "phase9-export-admin")
        website = await make_site(session, owner)
        await configure_usd_export_price(session, admin)
        exports = ExportService(session, MemoryObjectStorage())
        purchase = await exports.create_purchase(
            website.id, owner.id, owner.billing_country_code, "phase9-export-purchase-0001"
        )
        assert purchase.state == "CREATED" and purchase.amount_minor == 1900
        await ExportPriceService(session).configure(
            currency="USD", amount_minor=2900, active=True, configured_by_user_id=admin.id
        )
        replayed_purchase = await exports.create_purchase(
            website.id, owner.id, owner.billing_country_code, "phase9-export-purchase-0001"
        )
        assert replayed_purchase.id == purchase.id and replayed_purchase.amount_minor == 1900
        purchase, payment = await exports.checkout(purchase.id, owner.id)
        assert purchase.state == "PAYMENT_PENDING" and payment.purpose == "EXPORT"
        verified = VerifiedExportPayment(
            provider="TEST",
            provider_event_id=f"phase9-export-event-{uuid4().hex}",
            provider_payment_reference=f"phase9-export-payment-{uuid4().hex}",
            payment_id=payment.id,
            amount_minor=1900,
            currency="USD",
            raw_body_hash=uuid4().hex + uuid4().hex,
            evidence={"verified": 1},
        )
        paid = await PaymentService(session).process_export_payment(verified)
        duplicate = await PaymentService(session).process_export_payment(verified)
        assert paid.id == duplicate.id and paid.state == "GENERATING"
        assert (
            await session.scalar(
                select(func.count(PaymentEvent.id)).where(PaymentEvent.payment_id == payment.id)
            )
            == 1
        )
        event = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == purchase.id,
                OutboxEvent.event_type == "export.generate_requested",
            )
        )
        assert event is not None
        processed = await exports.process_outbox_event(event.id)
        assert processed.state == "PUBLISHED" and purchase.state == "READY"
        artifact = await exports.artifact_for_download(purchase.id, owner.id)
        payload = exports.storage.get_bytes(artifact.object_key)  # type: ignore[union-attr]
        with ZipFile(BytesIO(payload)) as archive:
            assert sorted(archive.namelist()) == ["README.txt", "index.html", "manifest.json"]
            assert b"Export-ready" in archive.read("index.html")
            assert b"phase9-test-secret" not in payload
            assert str(owner.id).encode() not in payload
        assert artifact.manifest["schema"] == "ZYLORA_WEBSITE_EXPORT_V1"
        intruder = await create_user(session, "phase9-export-intruder")
        with pytest.raises(AuthProblem):
            await exports.artifact_for_download(purchase.id, intruder.id)
        await session.rollback()


@pytest.mark.integration
async def test_export_rejects_missing_or_mismatched_payment_and_stale_owner_access() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "phase9-export-safe-owner")
        recipient = await create_user(session, "phase9-export-safe-recipient")
        admin = await create_user(session, "phase9-export-safe-admin")
        website = await make_site(session, owner)
        exports = ExportService(session, MemoryObjectStorage())
        with pytest.raises(AuthProblem, match="not available"):
            await exports.create_purchase(
                website.id, owner.id, owner.billing_country_code, "phase9-no-price-export-0001"
            )
        await configure_usd_export_price(session, admin)
        purchase = await exports.create_purchase(
            website.id, owner.id, owner.billing_country_code, "phase9-safe-export-0001"
        )
        _, payment = await exports.checkout(purchase.id, owner.id)
        invalid = VerifiedExportPayment(
            provider="TEST",
            provider_event_id=f"phase9-invalid-export-event-{uuid4().hex}",
            provider_payment_reference=f"phase9-invalid-export-payment-{uuid4().hex}",
            payment_id=payment.id,
            amount_minor=1,
            currency="USD",
            raw_body_hash=uuid4().hex + uuid4().hex,
            evidence={"verified": 1},
        )
        with pytest.raises(AuthProblem, match="amount"):
            await PaymentService(session).process_export_payment(invalid)
        assert purchase.state == "PAYMENT_PENDING"
        with pytest.raises(AuthProblem, match="verified payment"):
            await exports.queue_generation(purchase.id, owner.id, "phase9-payment-bypass")
        transfer = await OwnershipService(session).start_transfer(
            website.id,
            owner.id,
            recipient.normalized_email,
            TRANSFER_CONFIRMATION_VERSION,
            "phase9-export-stale-owner-transfer-0001",
            "phase9-export-stale-owner-transfer",
        )
        assert transfer.status == "COMPLETED"
        with pytest.raises(AuthProblem):
            await exports.get_for_owner(purchase.id, owner.id)
        assert (
            await session.scalar(select(ExportPurchase).where(ExportPurchase.id == purchase.id))
            is purchase
        )
        await session.rollback()


@pytest.mark.integration
async def test_export_worker_claims_only_ready_events_with_a_durable_lease() -> None:
    from zylora_worker import tasks

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    marker = f"phase9-export-worker-claim-{uuid4().hex}"
    event_id = uuid4()
    try:
        async with factory() as session:
            session.add(
                OutboxEvent(
                    aggregate_type="EXPORT_PURCHASE",
                    aggregate_id=uuid4(),
                    event_type="export.generate_requested",
                    payload={"purchase_id": str(uuid4())},
                    correlation_id=marker,
                )
            )
            await session.commit()
        claimed = await tasks._claim_export_events(100)
        assert len(claimed) >= 1
        async with factory() as session:
            event = await session.scalar(
                select(OutboxEvent).where(OutboxEvent.correlation_id == marker)
            )
            assert event is not None
            event_id = event.id
            assert str(event_id) in claimed
            assert event.lease_owner and event.leased_until
    finally:
        async with factory() as session:
            await session.execute(delete(OutboxEvent).where(OutboxEvent.correlation_id == marker))
            await session.commit()
