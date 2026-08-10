from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID, uuid4

from zylora_worker import __version__
from zylora_worker.celery_app import celery_app


class WorkerHealthResult(TypedDict):
    service: str
    status: str
    version: str
    request_id: str


@celery_app.task(name="zylora.operations.health", acks_late=True)  # type: ignore[untyped-decorator]
def worker_health(request_id: str) -> WorkerHealthResult:
    """Operational task used to verify real broker-to-worker execution."""

    if not request_id or len(request_id) > 128:
        raise ValueError("request_id must contain between 1 and 128 characters")
    return {
        "service": "zylora-worker",
        "status": "alive",
        "version": __version__,
        "request_id": request_id,
    }


async def _process_publication_event(event_id: UUID) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.session import get_engine
    from zylora_api.modules.publishing.artifacts import ArtifactBuilder
    from zylora_api.modules.publishing.providers import domain_provider_for
    from zylora_api.modules.publishing.runtime import publication_storage_for
    from zylora_api.modules.publishing.service import DeploymentService

    settings = get_settings()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        event = await DeploymentService(session).process_outbox_event(
            event_id,
            domain_provider_for(settings),
            ArtifactBuilder(publication_storage_for(settings)),
        )
        await session.commit()
        return event.state


@celery_app.task(name="zylora.publishing.process_outbox_event", acks_late=True)  # type: ignore[untyped-decorator]
def process_publication_event(event_id: str) -> str:
    """Process a single idempotent publication outbox event through the domain service."""

    return asyncio.run(_process_publication_event(UUID(event_id)))


async def _claim_publication_events(limit: int) -> list[str]:
    from sqlalchemy import or_, select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine

    now = datetime.now(UTC)
    owner = f"zylora-publisher:{uuid4()}"
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.state == "PENDING",
                        OutboxEvent.event_type.in_(
                            (
                                "deployment.publish_requested",
                                "deployment.rollback_requested",
                                "website.unpublish_requested",
                            )
                        ),
                        OutboxEvent.available_at <= now,
                        or_(
                            OutboxEvent.leased_until.is_(None),
                            OutboxEvent.leased_until < now,
                        ),
                    )
                    .order_by(OutboxEvent.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for event in events:
            event.lease_owner = owner
            event.leased_until = now + timedelta(minutes=5)
        await session.commit()
        return [str(event.id) for event in events]


@celery_app.task(name="zylora.publishing.dispatch_outbox", acks_late=True)  # type: ignore[untyped-decorator]
def dispatch_publication_events(limit: int = 50) -> int:
    """Lease publication events, then enqueue independently retryable event tasks."""

    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    event_ids = asyncio.run(_claim_publication_events(limit))
    for event_id in event_ids:
        process_publication_event.delay(event_id)
    return len(event_ids)


async def _process_export_event(event_id: UUID) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.session import get_engine
    from zylora_api.modules.commerce.exports import ExportService
    from zylora_api.modules.publishing.runtime import publication_storage_for

    settings = get_settings()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        event = await ExportService(
            session, publication_storage_for(settings)
        ).process_outbox_event(event_id)
        await session.commit()
        return event.state


@celery_app.task(name="zylora.exports.process_outbox_event", acks_late=True)  # type: ignore[untyped-decorator]
def process_export_event(event_id: str) -> str:
    """Process one idempotent paid Website-export generation event."""

    return asyncio.run(_process_export_event(UUID(event_id)))


async def _claim_export_events(limit: int) -> list[str]:
    from sqlalchemy import or_, select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine

    now = datetime.now(UTC)
    owner = f"zylora-exporter:{uuid4()}"
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.state == "PENDING",
                        OutboxEvent.event_type == "export.generate_requested",
                        OutboxEvent.available_at <= now,
                        or_(
                            OutboxEvent.leased_until.is_(None),
                            OutboxEvent.leased_until < now,
                        ),
                    )
                    .order_by(OutboxEvent.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for event in events:
            event.lease_owner = owner
            event.leased_until = now + timedelta(minutes=5)
        await session.commit()
        return [str(event.id) for event in events]


@celery_app.task(name="zylora.exports.dispatch_outbox", acks_late=True)  # type: ignore[untyped-decorator]
def dispatch_export_events(limit: int = 50) -> int:
    """Lease paid export intents, then enqueue independently retryable generation tasks."""

    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    event_ids = asyncio.run(_claim_export_events(limit))
    for event_id in event_ids:
        process_export_event.delay(event_id)
    return len(event_ids)


async def _process_chatbot_event(event_id: UUID) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.session import get_engine
    from zylora_api.modules.chatbot.indexing import KnowledgeIndexService
    from zylora_api.modules.publishing.runtime import publication_storage_for

    settings = get_settings()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        event = await KnowledgeIndexService(
            session, publication_storage_for(settings), settings
        ).process_outbox_event(event_id)
        await session.commit()
        return event.state


@celery_app.task(name="zylora.chatbot.process_outbox_event", acks_late=True)  # type: ignore[untyped-decorator]
def process_chatbot_event(event_id: str) -> str:
    """Build one isolated FAISS index through the durable chatbot outbox."""

    return asyncio.run(_process_chatbot_event(UUID(event_id)))


async def _claim_chatbot_events(limit: int) -> list[str]:
    from sqlalchemy import or_, select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine

    now = datetime.now(UTC)
    owner = f"zylora-chatbot:{uuid4()}"
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.state == "PENDING",
                        OutboxEvent.event_type.in_(
                            ("chatbot.index_requested", "chatbot.cleanup_requested")
                        ),
                        OutboxEvent.available_at <= now,
                        or_(
                            OutboxEvent.leased_until.is_(None),
                            OutboxEvent.leased_until < now,
                        ),
                    )
                    .order_by(OutboxEvent.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for event in events:
            event.lease_owner = owner
            event.leased_until = now + timedelta(minutes=5)
        await session.commit()
        return [str(event.id) for event in events]


@celery_app.task(name="zylora.chatbot.dispatch_outbox", acks_late=True)  # type: ignore[untyped-decorator]
def dispatch_chatbot_events(limit: int = 25) -> int:
    """Lease isolated knowledge-index jobs without making Redis authoritative."""

    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    event_ids = asyncio.run(_claim_chatbot_events(limit))
    for event_id in event_ids:
        process_chatbot_event.delay(event_id)
    return len(event_ids)


async def _process_transactional_email_event(event_id: UUID) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.session import get_engine
    from zylora_api.modules.auth.delivery import SMTPEmailSender
    from zylora_api.modules.auth.security import AuthCrypto
    from zylora_api.modules.notifications.email import TransactionalEmailService

    settings = get_settings()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        event = await TransactionalEmailService(
            session, AuthCrypto(settings.auth_secret)
        ).process_outbox_event(event_id, SMTPEmailSender(settings))
        await session.commit()
        return event.state


@celery_app.task(name="zylora.notifications.process_transactional_email", acks_late=True)  # type: ignore[untyped-decorator]
def process_transactional_email_event(event_id: str) -> str:
    """Deliver one encrypted transactional email through its durable outbox record."""

    return asyncio.run(_process_transactional_email_event(UUID(event_id)))


async def _claim_transactional_email_events(limit: int) -> list[str]:
    from sqlalchemy import or_, select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine

    now = datetime.now(UTC)
    owner = f"zylora-transactional-email:{uuid4()}"
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.state == "PENDING",
                        OutboxEvent.event_type == "transactional_email.send_requested",
                        OutboxEvent.available_at <= now,
                        or_(
                            OutboxEvent.leased_until.is_(None),
                            OutboxEvent.leased_until < now,
                        ),
                    )
                    .order_by(OutboxEvent.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for event in events:
            event.lease_owner = owner
            event.leased_until = now + timedelta(minutes=5)
        await session.commit()
        return [str(event.id) for event in events]


@celery_app.task(name="zylora.notifications.dispatch_transactional_email", acks_late=True)  # type: ignore[untyped-decorator]
def dispatch_transactional_email_events(limit: int = 50) -> int:
    """Lease retryable transactional email jobs without exposing provider delivery to requests."""

    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    event_ids = asyncio.run(_claim_transactional_email_events(limit))
    for event_id in event_ids:
        process_transactional_email_event.delay(event_id)
    return len(event_ids)


async def _process_campaign_event(event_id: UUID) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.session import get_engine
    from zylora_api.modules.auth.delivery import SMTPEmailSender
    from zylora_api.modules.auth.security import AuthCrypto
    from zylora_api.modules.campaigns.service import CampaignService

    settings = get_settings()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        event = await CampaignService(
            session,
            AuthCrypto(settings.auth_secret),
            public_origin=settings.allowed_origins[0],
        ).process_outbox_event(event_id, SMTPEmailSender(settings))
        await session.commit()
        return event.state


@celery_app.task(name="zylora.campaigns.process_delivery", acks_late=True)  # type: ignore[untyped-decorator]
def process_campaign_event(event_id: str) -> str:
    return asyncio.run(_process_campaign_event(UUID(event_id)))


async def _claim_campaign_events(limit: int) -> list[str]:
    from sqlalchemy import or_, select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine

    now = datetime.now(UTC)
    owner = f"zylora-campaigns:{uuid4()}"
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.state == "PENDING",
                        OutboxEvent.event_type == "campaign.delivery_requested",
                        OutboxEvent.available_at <= now,
                        or_(OutboxEvent.leased_until.is_(None), OutboxEvent.leased_until < now),
                    )
                    .order_by(OutboxEvent.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for event in events:
            event.lease_owner = owner
            event.leased_until = now + timedelta(minutes=5)
        await session.commit()
        return [str(event.id) for event in events]


@celery_app.task(name="zylora.campaigns.dispatch_deliveries", acks_late=True)  # type: ignore[untyped-decorator]
def dispatch_campaign_events(limit: int = 50) -> int:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    event_ids = asyncio.run(_claim_campaign_events(limit))
    for event_id in event_ids:
        process_campaign_event.delay(event_id)
    return len(event_ids)


async def _start_due_campaigns(limit: int) -> int:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.session import get_engine
    from zylora_api.modules.auth.security import AuthCrypto
    from zylora_api.modules.campaigns.service import CampaignService

    settings = get_settings()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        service = CampaignService(session, AuthCrypto(settings.auth_secret))
        campaign_ids = await service.due_campaign_ids(limit)
        for campaign_id in campaign_ids:
            await service.start(campaign_id, correlation_id="scheduled-campaign")
        await session.commit()
        return len(campaign_ids)


@celery_app.task(name="zylora.campaigns.start_scheduled", acks_late=True)  # type: ignore[untyped-decorator]
def start_due_campaigns(limit: int = 25) -> int:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    return asyncio.run(_start_due_campaigns(limit))


async def _publish_due_blog_posts(limit: int) -> int:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.session import get_engine
    from zylora_api.modules.blog.service import BlogService

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        service = BlogService(session)
        post_ids = await service.due_post_ids(limit)
        for post_id in post_ids:
            await service.publish(post_id, correlation_id="scheduled-blog-publication")
        await session.commit()
        return len(post_ids)


@celery_app.task(name="zylora.blog.publish_scheduled", acks_late=True)  # type: ignore[untyped-decorator]
def publish_due_blog_posts(limit: int = 25) -> int:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    return asyncio.run(_publish_due_blog_posts(limit))


async def _refresh_analytics(limit: int) -> int:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.session import get_engine
    from zylora_api.modules.analytics.service import AnalyticsService

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        refreshed = await AnalyticsService(session).refresh_recent(limit)
        await session.commit()
        return refreshed


@celery_app.task(name="zylora.analytics.refresh", acks_late=True)  # type: ignore[untyped-decorator]
def refresh_analytics(limit: int = 100) -> int:
    """Recompute recent timezone-aware analytics rollups in background work only."""

    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    return asyncio.run(_refresh_analytics(limit))
