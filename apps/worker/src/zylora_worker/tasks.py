from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from time import perf_counter
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
            ArtifactBuilder(
                publication_storage_for(settings),
                turnstile_site_key=settings.turnstile_site_key
                if settings.turnstile_enabled
                else None,
            ),
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
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine
    from zylora_api.modules.chatbot.indexing import KnowledgeIndexService
    from zylora_api.modules.knowledge.service import KnowledgeSourceService
    from zylora_api.modules.publishing.runtime import publication_storage_for

    settings = get_settings()
    storage = publication_storage_for(settings)
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        kind = await session.scalar(
            select(OutboxEvent.event_type).where(OutboxEvent.id == event_id)
        )
        if kind in {"knowledge.source_ingest_requested", "knowledge.source_delete_requested"}:
            event = await KnowledgeSourceService(session, storage, settings).process_outbox_event(
                event_id
            )
        else:
            event = await KnowledgeIndexService(session, storage, settings).process_outbox_event(
                event_id
            )
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
                            (
                                "chatbot.index_requested",
                                "chatbot.cleanup_requested",
                                "knowledge.source_ingest_requested",
                                "knowledge.source_delete_requested",
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


async def _process_lead_channel_event(event_id: UUID) -> str:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine
    from zylora_api.modules.auth.security import AuthCrypto
    from zylora_api.modules.notifications.lead import LeadOwnerNotificationService
    from zylora_api.modules.notifications.whatsapp import WhatsAppNotificationService

    settings = get_settings()
    crypto = AuthCrypto(settings.auth_secret)
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        kind = await session.scalar(
            select(OutboxEvent.event_type).where(OutboxEvent.id == event_id)
        )
        if kind == "lead.owner_notification_requested":
            event = await LeadOwnerNotificationService(session, crypto).process_outbox_event(
                event_id
            )
        else:
            event = await WhatsAppNotificationService(
                session, crypto, settings
            ).process_outbox_event(event_id)
        await session.commit()
        return event.state


@celery_app.task(name="zylora.notifications.process_lead_channel", acks_late=True)  # type: ignore[untyped-decorator]
def process_lead_channel_event(event_id: str) -> str:
    """Deliver one idempotent Lead email intent or Twilio WhatsApp notification."""

    return asyncio.run(_process_lead_channel_event(UUID(event_id)))


async def _claim_lead_channel_events(limit: int) -> list[str]:
    from sqlalchemy import or_, select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine

    now = datetime.now(UTC)
    owner = f"zylora-lead-channels:{uuid4()}"
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
                                "lead.owner_notification_requested",
                                "lead.whatsapp_notification_requested",
                                "whatsapp.notification_requested",
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


@celery_app.task(name="zylora.notifications.dispatch_lead_channels", acks_late=True)  # type: ignore[untyped-decorator]
def dispatch_lead_channel_events(limit: int = 50) -> int:
    """Lease Lead notification intents without making Redis authoritative."""

    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    event_ids = asyncio.run(_claim_lead_channel_events(limit))
    for event_id in event_ids:
        process_lead_channel_event.delay(event_id)
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


async def _run_activation_maintenance(limit: int) -> dict[str, int]:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.session import get_engine
    from zylora_api.modules.analytics.activation import ProductAnalyticsService
    from zylora_api.modules.auth.security import AuthCrypto

    settings = get_settings()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        service = ProductAnalyticsService(session)
        digests = await service.queue_monthly_digests(AuthCrypto(settings.auth_secret), limit)
        zero_lead = await service.process_zero_lead_checkpoints(limit)
        await session.commit()
        return {"monthly_digests_queued": digests, "zero_lead_notifications": zero_lead}


@celery_app.task(name="zylora.analytics.activation_maintenance", acks_late=True)  # type: ignore[untyped-decorator]
def run_activation_maintenance(limit: int = 100) -> dict[str, int]:
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    return asyncio.run(_run_activation_maintenance(limit))


async def _execute_ai_generation(job_id: UUID, worker_id: str) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.session import get_engine
    from zylora_api.modules.ai_builder.artifacts import GenerationArtifactVerifier
    from zylora_api.modules.ai_builder.client import AiBuilderClient, AiBuilderError
    from zylora_api.modules.ai_builder.service import AiSiteProjectService
    from zylora_api.modules.auth.security import AuthCrypto
    from zylora_api.modules.publishing.runtime import publication_storage_for

    settings = get_settings()
    crypto = AuthCrypto(settings.auth_secret)
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        claim = await AiSiteProjectService(session, crypto, settings).claim(job_id, worker_id)
        await session.commit()
    if not claim:
        return "SKIPPED"

    logger = logging.getLogger("zylora.ai_builder")
    started = perf_counter()
    logger.info(
        "ai_generation_started",
        extra={
            "job_id": str(claim.job_id),
            "project_id": str(claim.project_id),
            "generation_id": str(claim.generation_id),
            "worker_id": worker_id,
            "attempt": claim.attempt,
            "correlation_id": claim.correlation_id,
            "state_transition": "QUEUED->GENERATING",
        },
    )
    try:
        result = await AiBuilderClient(settings).execute(
            generation_id=claim.generation_id,
            project_id=claim.project_id,
            owner_user_id=claim.owner_user_id,
            prompt=claim.prompt,
            lease_token=claim.lease_token,
        )
        verifier = GenerationArtifactVerifier(publication_storage_for(settings), settings)
        await asyncio.to_thread(
            verifier.verify,
            result.artifact,
            owner_user_id=claim.owner_user_id,
            project_id=claim.project_id,
            generation_id=claim.generation_id,
        )
    except AiBuilderError as error:
        async with factory() as session:
            await AiSiteProjectService(session, crypto, settings).fail(
                claim.job_id,
                claim.lease_token,
                error_code=error.code,
                retryable=error.retryable,
            )
            await session.commit()
        logger.warning(
            "ai_generation_failed",
            extra={
                "job_id": str(claim.job_id),
                "project_id": str(claim.project_id),
                "generation_id": str(claim.generation_id),
                "worker_id": worker_id,
                "attempt": claim.attempt,
                "correlation_id": claim.correlation_id,
                "duration_ms": int((perf_counter() - started) * 1000),
                "outcome": "retry" if error.retryable else "failed",
                "safe_error_code": error.code,
            },
        )
        return "RETRY_WAIT" if error.retryable else "FAILED"
    except Exception:
        async with factory() as session:
            await AiSiteProjectService(session, crypto, settings).fail(
                claim.job_id,
                claim.lease_token,
                error_code="INTERNAL_GENERATION_ERROR",
                retryable=True,
            )
            await session.commit()
        logger.exception(
            "ai_generation_internal_failure",
            extra={
                "job_id": str(claim.job_id),
                "project_id": str(claim.project_id),
                "generation_id": str(claim.generation_id),
                "worker_id": worker_id,
                "attempt": claim.attempt,
                "correlation_id": claim.correlation_id,
                "duration_ms": int((perf_counter() - started) * 1000),
                "outcome": "retry",
                "safe_error_code": "INTERNAL_GENERATION_ERROR",
            },
        )
        return "RETRY_WAIT"

    async with factory() as session:
        completed = await AiSiteProjectService(session, crypto, settings).complete(
            claim.job_id, claim.lease_token, result
        )
        await session.commit()
    if not completed:
        return "STALE_RESULT"
    logger.info(
        "ai_generation_completed",
        extra={
            "job_id": str(claim.job_id),
            "project_id": str(claim.project_id),
            "generation_id": str(claim.generation_id),
            "worker_id": worker_id,
            "attempt": claim.attempt,
            "correlation_id": claim.correlation_id,
            "duration_ms": int((perf_counter() - started) * 1000),
            "artifact_bytes": result.artifact.size_bytes,
            "outcome": "completed",
            "state_transition": "STORING->COMPLETED",
        },
    )
    return "COMPLETED"


@celery_app.task(name="zylora.ai_builder.execute_generation", acks_late=True)  # type: ignore[untyped-decorator]
def execute_ai_generation(job_id: str) -> str:
    """Execute one DB-leased generation; duplicate deliveries are safe no-ops."""

    worker_id = f"ai-generation:{uuid4()}"
    return asyncio.run(_execute_ai_generation(UUID(job_id), worker_id))


async def _claim_ai_generation_events(limit: int) -> list[tuple[UUID, UUID, str]]:
    from sqlalchemy import or_, select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine

    now = datetime.now(UTC)
    owner = f"ai-builder-dispatch:{uuid4()}"
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.state == "PENDING",
                        OutboxEvent.event_type == "ai_generation.execute_requested",
                        OutboxEvent.available_at <= now,
                        or_(OutboxEvent.leased_until.is_(None), OutboxEvent.leased_until < now),
                    )
                    .order_by(OutboxEvent.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        claimed: list[tuple[UUID, UUID, str]] = []
        for event in events:
            job_id = event.payload.get("job_id")
            if not isinstance(job_id, str):
                event.state = "FAILED"
                event.last_error_code = "ai_generation_job_reference_invalid"
                continue
            event.lease_owner = owner
            event.leased_until = now + timedelta(minutes=2)
            claimed.append((event.id, UUID(job_id), owner))
        await session.commit()
        return claimed


async def _finish_ai_generation_dispatch(
    event_id: UUID, lease_owner: str, *, delivered: bool
) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.db.models import OutboxEvent
    from zylora_api.db.session import get_engine

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if not event or event.state != "PENDING" or event.lease_owner != lease_owner:
            return
        now = datetime.now(UTC)
        if delivered:
            event.state = "PUBLISHED"
            event.published_at = now
            event.last_error_code = None
        else:
            event.attempts += 1
            event.last_error_code = "ai_generation_broker_unavailable"
            event.available_at = now + timedelta(seconds=min(300, 10 * (2**event.attempts)))
            if event.attempts >= 10:
                event.state = "FAILED"
        event.lease_owner = None
        event.leased_until = None
        await session.commit()


@celery_app.task(name="zylora.ai_builder.dispatch_outbox", acks_late=True)  # type: ignore[untyped-decorator]
def dispatch_ai_generation_events(limit: int = 25) -> int:
    """Dispatch ID-only outbox records; broker acceptance is recorded transactionally."""

    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    events = asyncio.run(_claim_ai_generation_events(limit))
    delivered = 0
    for event_id, job_id, owner in events:
        accepted = False
        try:
            execute_ai_generation.delay(str(job_id))
            accepted = True
            delivered += 1
        finally:
            asyncio.run(_finish_ai_generation_dispatch(event_id, owner, delivered=accepted))
    return delivered


async def _recover_ai_generation_jobs(limit: int) -> list[UUID]:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from zylora_api.core.config import get_settings
    from zylora_api.db.session import get_engine
    from zylora_api.modules.ai_builder.service import AiSiteProjectService
    from zylora_api.modules.auth.security import AuthCrypto

    settings = get_settings()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        jobs = await AiSiteProjectService(
            session, AuthCrypto(settings.auth_secret), settings
        ).recover_stale(limit)
        await session.commit()
        return jobs


@celery_app.task(name="zylora.ai_builder.recover_stale", acks_late=True)  # type: ignore[untyped-decorator]
def recover_ai_generation_jobs(limit: int = 100) -> int:
    """Requeue due retries and expired leases after worker/builder process loss."""

    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    job_ids = asyncio.run(_recover_ai_generation_jobs(limit))
    for job_id in job_ids:
        execute_ai_generation.delay(str(job_id))
    return len(job_ids)
