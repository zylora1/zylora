from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import User
from zylora_api.db.chatbot_models import (
    Chatbot,
    ChatbotKnowledgeChunk,
    ChatbotKnowledgeIndex,
    ChatMessage,
)
from zylora_api.db.knowledge_models import KnowledgeSource
from zylora_api.db.lead_models import (
    AnalyticsEvent,
    Lead,
    LeadCreditLedger,
    Notification,
    TransactionalEmail,
)
from zylora_api.db.models import OutboxEvent
from zylora_api.db.session import get_engine
from zylora_api.db.website_models import Website
from zylora_api.db.whatsapp_models import WhatsAppNotificationSetting
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.chatbot.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderError,
)
from zylora_api.modules.chatbot.generation import INSUFFICIENT_KNOWLEDGE_FALLBACK
from zylora_api.modules.chatbot.indexing import KnowledgeIndexService
from zylora_api.modules.chatbot.service import ChatbotService
from zylora_api.modules.commerce.ownership import OwnershipService
from zylora_api.modules.commerce.quotas import LeadService, NotificationQuotaService
from zylora_api.modules.knowledge.service import KnowledgeSourceService
from zylora_api.modules.leads.credits import (
    ALLOW_DEBT,
    REJECT_NEW,
    CreditLedgerService,
    LeadCreditPolicyService,
)
from zylora_api.modules.notifications.lead import LeadOwnerNotificationService
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.websites.service import WebsiteService
from zylora_api.storage.memory import MemoryObjectStorage


def document(name: str, distinctive_text: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "registry_version": "1.0.0",
        "metadata": {"name": name, "description": distinctive_text, "language": "en"},
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
                "id": f"home-{name.casefold().replace(' ', '-')}",
                "slug": "home",
                "label": "Home",
                "parent_page_id": None,
                "sort_order": 0,
                "is_home": True,
                "show_in_navigation": True,
                "status": "ACTIVE",
                "seo": {"title": name, "description": distinctive_text},
                "components": [
                    {
                        "id": "hero",
                        "type": "HERO",
                        "props": {"heading": name, "body": distinctive_text},
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


async def published_site(session: AsyncSession, name: str, content: str) -> tuple[User, Website]:
    suffix = uuid4().hex
    owner = User(
        account_type="USER",
        normalized_email=f"phase10-{suffix}@example.com",
        display_email=f"phase10-{suffix}@example.com",
        status="ACTIVE",
        verified_at=datetime.now(UTC),
        billing_country_code="ZZ",
    )
    session.add(owner)
    await session.flush()
    templates = TemplateService(session, AuthCrypto("phase10-secret-long-enough-for-tests"))
    template = await templates.create(
        TemplateCreateRequest(
            slug=f"phase10-{suffix}",
            name=name,
            summary="Phase 10 test template.",
            category_slug=f"phase10-category-{suffix}",
            category_name="Phase 10",
            category_description="Phase 10 test category.",
            tags=[f"phase10-{suffix}"],
            featured_order=100,
        ),
        owner.id,
    )
    await templates.add_version(template.id, document(name, content), owner.id)
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
async def test_lead_capture_is_atomic_idempotent_and_policy_driven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, website = await published_site(
            session, "Lead Studio", "We answer enquiries quickly."
        )
        await LeadCreditPolicyService(session).configure(ALLOW_DEBT)
        session.add(
            WhatsAppNotificationSetting(
                owner_user_id=owner.id,
                phone_ciphertext=b"encrypted-test-phone",
                phone_hash=uuid4().bytes + uuid4().bytes,
                phone_last4="3210",
                country_code="IN",
                enabled=True,
                status="READY",
                consented_at=datetime.now(UTC),
            )
        )
        await session.flush()

        async def reserve_whatsapp(
            _service: NotificationQuotaService,
            _user_id: object,
            _country_code: str,
            _operation_id: object,
        ) -> bool:
            return True

        monkeypatch.setattr(NotificationQuotaService, "reserve_whatsapp", reserve_whatsapp)
        first = await LeadService(session).capture(
            website_id=website.id,
            source="FORM",
            idempotency_key="phase10-form-lead-0001",
            name="Ada Visitor",
            email="ada@example.com",
            phone=None,
            enquiry="Please call me.",
            owner_country_code="ZZ",
            correlation_id="phase10-lead-first",
            page_path="/contact",
            consent={"contact": True},
        )
        duplicate = await LeadService(session).capture(
            website_id=website.id,
            source="FORM",
            idempotency_key="phase10-form-lead-0001",
            name="Ada Visitor",
            email="ada@example.com",
            phone=None,
            enquiry="Please call me.",
            owner_country_code="ZZ",
            correlation_id="phase10-lead-retry",
            page_path="/contact",
            consent={"contact": True},
        )
        assert duplicate.duplicate and duplicate.lead.id == first.lead.id
        assert (
            await session.scalar(select(func.count(Lead.id)).where(Lead.website_id == website.id))
            == 1
        )
        assert (
            await session.scalar(
                select(func.count(LeadCreditLedger.id)).where(
                    LeadCreditLedger.lead_id == first.lead.id,
                    LeadCreditLedger.delta == -1,
                )
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count(Notification.id)).where(Notification.resource_id == first.lead.id)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count(AnalyticsEvent.id)).where(
                    AnalyticsEvent.idempotency_key == f"lead:{first.lead.id}"
                )
            )
            == 1
        )
        owner_email_event = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == first.lead.id,
                OutboxEvent.event_type == "lead.owner_notification_requested",
            )
        )
        whatsapp_event_count = await session.scalar(
            select(func.count(OutboxEvent.id)).where(
                OutboxEvent.aggregate_id == first.lead.id,
                OutboxEvent.event_type == "lead.whatsapp_notification_requested",
            )
        )
        assert owner_email_event is not None
        assert whatsapp_event_count == 1
        assert first.lead.whatsapp_notification_queued is True
        processed_email = await LeadOwnerNotificationService(
            session, AuthCrypto("phase10-lead-email-secret-long-enough")
        ).process_outbox_event(owner_email_event.id)
        assert processed_email.state == "PUBLISHED"
        assert (
            await session.scalar(
                select(func.count(TransactionalEmail.id)).where(
                    TransactionalEmail.resource_id == first.lead.id,
                    TransactionalEmail.kind == "LEAD_OWNER_ALERT",
                )
            )
            == 1
        )

        assert await CreditLedgerService(session).balance_for(owner.id) == -1
        assert (await LeadCreditPolicyService(session).current()).policy == ALLOW_DEBT
        await LeadCreditPolicyService(session).configure(REJECT_NEW)
        with pytest.raises(AuthProblem, match="temporarily unavailable"):
            await LeadService(session).capture(
                website_id=website.id,
                source="FORM",
                idempotency_key="phase10-rejected-lead-0002",
                name="Blocked Visitor",
                email=None,
                phone=None,
                enquiry="A new enquiry.",
                owner_country_code="ZZ",
                correlation_id="phase10-lead-rejected",
            )
        assert (
            await session.scalar(select(func.count(Lead.id)).where(Lead.website_id == website.id))
            == 1
        )
        await LeadCreditPolicyService(session).configure(ALLOW_DEBT)
        await session.commit()


@pytest.mark.integration
async def test_concurrent_lead_retry_creates_one_lead_and_one_debit() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as setup:
        _, website = await published_site(
            setup, "Concurrent Studio", "Concurrent lead information."
        )
        website_id = website.id
        await LeadCreditPolicyService(setup).configure(ALLOW_DEBT)
        await setup.commit()

    async def submit() -> bool:
        async with factory() as session:
            result = await LeadService(session).capture(
                website_id=website_id,
                source="FORM",
                idempotency_key="phase10-concurrent-lead-0001",
                name="Concurrent Visitor",
                email="concurrent@example.com",
                phone=None,
                enquiry="Please help.",
                owner_country_code="ZZ",
                correlation_id=f"phase10-concurrent-{uuid4()}",
            )
            await session.commit()
            return result.duplicate

    results = await asyncio.gather(submit(), submit())
    assert sorted(results) == [False, True]
    async with factory() as verify:
        lead = await verify.scalar(
            select(Lead).where(
                Lead.website_id == website_id,
                Lead.idempotency_key == "phase10-concurrent-lead-0001",
            )
        )
        assert lead is not None
        assert (
            await verify.scalar(
                select(func.count(LeadCreditLedger.id)).where(LeadCreditLedger.lead_id == lead.id)
            )
            == 1
        )


@pytest.mark.integration
async def test_faiss_index_and_conversations_are_website_isolated() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    settings = Settings(
        environment="test",
        storage_provider="memory",
        chatbot_embedding_dimension=64,
        chatbot_embedding_model="deterministic-test-v1",
        _env_file=None,
    )
    embeddings = DeterministicEmbeddingProvider(64)
    storage = MemoryObjectStorage()
    async with factory() as session:
        owner_a, website_a = await published_site(
            session, "Dental A", "Dental A provides zirconium implants and emergency dental care."
        )
        owner_b, website_b = await published_site(
            session, "Bakery B", "Bakery B bakes sourdough bread and custom cakes."
        )
        indexer = KnowledgeIndexService(session, storage, settings, embeddings)
        requested_a = await indexer.request_for_published_website(
            website_a, website_a.published_version_id, "phase10-index-a"
        )
        requested_b = await indexer.request_for_published_website(
            website_b, website_b.published_version_id, "phase10-index-b"
        )
        event_a = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == requested_a.id)
        )
        event_b = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == requested_b.id)
        )
        assert event_a is not None and event_b is not None
        assert (await indexer.process_outbox_event(event_a.id)).state == "PUBLISHED"
        assert (await indexer.process_outbox_event(event_b.id)).state == "PUBLISHED"
        index_a = await session.get(ChatbotKnowledgeIndex, requested_a.id)
        index_b = await session.get(ChatbotKnowledgeIndex, requested_b.id)
        assert index_a and index_b and index_a.state == index_b.state == "ACTIVE"
        assert index_a.owner_user_id == owner_a.id and index_b.owner_user_id == owner_b.id
        chats = ChatbotService(session, storage, embeddings)
        notification_count_before = int(
            await session.scalar(
                select(func.count(OutboxEvent.id)).where(
                    OutboxEvent.event_type.in_(
                        (
                            "lead.owner_notification_requested",
                            "lead.whatsapp_notification_requested",
                        )
                    )
                )
            )
            or 0
        )
        conversation = await chats.start_conversation(website_a.id)
        reply = await chats.reply(
            website_id=website_a.id,
            conversation_id=conversation.conversation.id,
            access_token=conversation.access_token,
            message="Tell me about dental implants.",
        )
        assert "zirconium implants" in reply.answer.casefold()
        assert all(path == "/" for path in reply.source_paths)
        assert conversation.conversation.lead_id is None
        assert (
            await session.scalar(select(func.count(Lead.id)).where(Lead.website_id == website_a.id))
            == 0
        )
        assert (
            await session.scalar(
                select(func.count(OutboxEvent.id)).where(
                    OutboxEvent.event_type.in_(
                        (
                            "lead.owner_notification_requested",
                            "lead.whatsapp_notification_requested",
                        )
                    )
                )
            )
            == notification_count_before
        )
        fallback_settings = Settings(
            _env_file=None,
            environment="test",
            storage_provider="memory",
            chatbot_embedding_model=embeddings.model,
            chatbot_embedding_dimension=64,
            chatbot_relevance_threshold=1.0,
        )
        fallback_chats = ChatbotService(session, storage, embeddings, settings=fallback_settings)
        fallback_conversation = await fallback_chats.start_conversation(website_a.id)
        fallback = await fallback_chats.reply(
            website_id=website_a.id,
            conversation_id=fallback_conversation.conversation.id,
            access_token=fallback_conversation.access_token,
            message="Do you sell interplanetary spacecraft?",
        )
        assert fallback.answer == INSUFFICIENT_KNOWLEDGE_FALLBACK
        with pytest.raises(AuthProblem, match="Conversation not found"):
            await chats.reply(
                website_id=website_b.id,
                conversation_id=conversation.conversation.id,
                access_token=conversation.access_token,
                message="Tell me about bread.",
            )
        assert (
            await session.scalar(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.conversation_id == conversation.conversation.id
                )
            )
            == 2
        )
        await session.commit()


@pytest.mark.integration
async def test_transfer_invalidates_and_deletes_the_previous_owner_faiss_index() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    settings = Settings(
        environment="test",
        storage_provider="memory",
        chatbot_embedding_dimension=64,
        chatbot_embedding_model="deterministic-test-v1",
        _env_file=None,
    )
    embeddings = DeterministicEmbeddingProvider(64)
    storage = MemoryObjectStorage()
    async with factory() as session:
        owner, website = await published_site(
            session, "Transfer Dental", "Transfer-only implant knowledge."
        )
        indexer = KnowledgeIndexService(session, storage, settings, embeddings)
        requested = await indexer.request_for_published_website(
            website, website.published_version_id, "phase10-transfer-index"
        )
        event = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == requested.id,
                OutboxEvent.event_type == "chatbot.index_requested",
            )
        )
        assert event is not None
        assert (await indexer.process_outbox_event(event.id)).state == "PUBLISHED"
        index = await session.get(ChatbotKnowledgeIndex, requested.id)
        assert index and index.artifact_key
        artifact_key = index.artifact_key
        recipient = User(
            account_type="USER",
            normalized_email=f"recipient-{uuid4().hex}@example.com",
            display_email=f"recipient-{uuid4().hex}@example.com",
            status="ACTIVE",
            verified_at=datetime.now(UTC),
            billing_country_code="ZZ",
        )
        session.add(recipient)
        website.status = "DRAFT"
        website.live_owner_user_id = None
        website.active_deployment_id = None
        await session.flush()
        transfer = await OwnershipService(session).transfer(
            website.id,
            owner.id,
            recipient.normalized_email,
            "phase10-transfer-cleanup-0001",
        )
        assert transfer.status == "COMPLETED"
        chatbot = await session.scalar(select(Chatbot).where(Chatbot.website_id == website.id))
        assert chatbot and chatbot.state == "DISABLED" and chatbot.active_index_id is None
        assert index.state == "DELETED"
        cleanup = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == index.id,
                OutboxEvent.event_type == "chatbot.cleanup_requested",
            )
        )
        assert cleanup is not None
        assert (await indexer.process_outbox_event(cleanup.id)).state == "PUBLISHED"
        with pytest.raises(KeyError):
            storage.get_bytes(artifact_key)
        await session.commit()


@pytest.mark.integration
async def test_credit_adjustments_are_atomic_and_idempotent() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, _ = await published_site(session, "Credit Studio", "Credit control test content.")
        credits = CreditLedgerService(session)
        granted = await credits.adjust(
            user_id=owner.id,
            actor_user_id=owner.id,
            delta=25,
            idempotency_key="phase10-credit-grant-0001",
            reason="Launch grant",
        )
        retried = await credits.adjust(
            user_id=owner.id,
            actor_user_id=owner.id,
            delta=25,
            idempotency_key="phase10-credit-grant-0001",
            reason="Launch grant",
        )
        assert granted.id == retried.id
        assert granted.entry_type == "ADMIN_GRANT" and granted.resulting_balance == 25
        assert await credits.balance_for(owner.id) == 25
        with pytest.raises(AuthProblem, match="idempotency key"):
            await credits.adjust(
                user_id=owner.id,
                actor_user_id=owner.id,
                delta=20,
                idempotency_key="phase10-credit-grant-0001",
                reason="Launch grant",
            )
        with pytest.raises(AuthProblem, match="adjustment is invalid"):
            await credits.adjust(
                user_id=owner.id,
                actor_user_id=owner.id,
                delta=0,
                idempotency_key="phase10-credit-invalid-0002",
                reason="No-op",
            )
        with pytest.raises(AuthProblem, match="valid adjustment reason"):
            await credits.adjust(
                user_id=owner.id,
                actor_user_id=owner.id,
                delta=-1,
                idempotency_key="phase10-credit-invalid-0003",
                reason=" ",
            )
        with pytest.raises(AuthProblem, match="User not found"):
            await credits.adjust(
                user_id=uuid4(),
                actor_user_id=owner.id,
                delta=1,
                idempotency_key="phase10-credit-missing-user-0004",
                reason="Missing user",
            )
        await session.commit()


@pytest.mark.integration
async def test_failed_chatbot_jobs_and_corrupt_artifacts_never_create_partial_messages() -> None:
    class FailingEmbeddings:
        model = "failing-test-provider"

        async def embed(self, _: list[str]) -> list[list[float]]:
            raise EmbeddingProviderError

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    settings = Settings(
        environment="test",
        storage_provider="memory",
        chatbot_embedding_dimension=64,
        chatbot_embedding_model="deterministic-test-v1",
        _env_file=None,
    )
    async with factory() as session:
        _, failed_website = await published_site(
            session, "Failure Studio", "This content must not produce an active failed index."
        )
        failing_indexer = KnowledgeIndexService(
            session, MemoryObjectStorage(), settings, FailingEmbeddings()
        )
        requested = await failing_indexer.request_for_published_website(
            failed_website, failed_website.published_version_id, "phase10-index-failure-0001"
        )
        assert (
            await failing_indexer.request_for_published_website(
                failed_website, failed_website.published_version_id, "phase10-index-failure-retry"
            )
        ).id == requested.id
        event = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == requested.id,
                OutboxEvent.event_type == "chatbot.index_requested",
            )
        )
        assert event is not None
        assert (await failing_indexer.process_outbox_event(event.id)).state == "FAILED"
        failed = await session.get(ChatbotKnowledgeIndex, requested.id)
        failed_chatbot = await session.scalar(
            select(Chatbot).where(Chatbot.website_id == failed_website.id)
        )
        assert (
            failed
            and failed.state == "FAILED"
            and failed.failure_code == "knowledge_index_build_failed"
        )
        assert failed_chatbot and failed_chatbot.state == "FAILED"
        unavailable_chats = ChatbotService(
            session, MemoryObjectStorage(), DeterministicEmbeddingProvider(64)
        )
        with pytest.raises(AuthProblem, match="chatbot is not ready"):
            await unavailable_chats.start_conversation(failed_website.id)
        with pytest.raises(AuthProblem, match="Published Website not found"):
            await unavailable_chats.start_conversation(uuid4())
        assert failed_chatbot.active_index_id is None

        unsupported = OutboxEvent(
            aggregate_type="CHATBOT_KNOWLEDGE_INDEX",
            aggregate_id=requested.id,
            event_type="chatbot.unsupported",
            payload={},
            correlation_id="phase10-index-unsupported-0002",
        )
        session.add(unsupported)
        await session.flush()
        assert (await failing_indexer.process_outbox_event(unsupported.id)).state == "FAILED"
        assert unsupported.last_error_code == "chatbot_event_failed"

        _, website = await published_site(
            session, "Artifact Studio", "Private artifact integrity test content."
        )
        storage = MemoryObjectStorage()
        ready_indexer = KnowledgeIndexService(
            session, storage, settings, DeterministicEmbeddingProvider(64)
        )
        ready = await ready_indexer.request_for_published_website(
            website, website.published_version_id, "phase10-artifact-ready-0003"
        )
        ready_event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == ready.id)
        )
        assert ready_event is not None
        assert (await ready_indexer.process_outbox_event(ready_event.id)).state == "PUBLISHED"
        index = await session.get(ChatbotKnowledgeIndex, ready.id)
        assert index and index.artifact_key and index.artifact_checksum
        chats = ChatbotService(session, storage, DeterministicEmbeddingProvider(64))
        conversation = await chats.start_conversation(website.id, {"chat": True})
        with pytest.raises(AuthProblem, match="Conversation not found"):
            await chats._conversation(website.id, conversation.conversation.id, "")
        with pytest.raises(AuthProblem, match="Conversation not found"):
            await chats._conversation(website.id, conversation.conversation.id, "wrong-token")
        with pytest.raises(AuthProblem, match="Enter a message"):
            await chats.reply(
                website_id=website.id,
                conversation_id=conversation.conversation.id,
                access_token=conversation.access_token,
                message="   ",
            )
        expected_checksum = index.artifact_checksum
        index.artifact_checksum = "0" * 64
        with pytest.raises(AuthProblem, match="chatbot is unavailable"):
            await chats.reply(
                website_id=website.id,
                conversation_id=conversation.conversation.id,
                access_token=conversation.access_token,
                message="Private integrity content",
            )
        index.artifact_checksum = expected_checksum
        storage.delete(index.artifact_key)
        with pytest.raises(AuthProblem, match="chatbot is not ready"):
            await chats.reply(
                website_id=website.id,
                conversation_id=conversation.conversation.id,
                access_token=conversation.access_token,
                message="Private integrity content",
            )
        assert (
            await session.scalar(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.conversation_id == conversation.conversation.id
                )
            )
            == 0
        )
        await session.commit()


@pytest.mark.integration
async def test_uploaded_knowledge_is_tenant_isolated_and_rebuilds_atomically() -> None:
    class FailingEmbeddings:
        model = "deterministic-test-v1"

        async def embed(self, _texts: list[str]) -> list[list[float]]:
            raise EmbeddingProviderError

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        environment="test",
        storage_provider="memory",
        knowledge_ingestion_enabled=True,
        ai_provider="openai",
        document_scanner_provider="test",
        openai_api_key="server-only-integration-test-key",
        chatbot_embedding_model="deterministic-test-v1",
        chatbot_embedding_dimension=64,
        chatbot_relevance_threshold=0.0,
    )
    embeddings = DeterministicEmbeddingProvider(64)
    storage = MemoryObjectStorage()
    async with factory() as session:
        owner_a, website_a = await published_site(
            session, "Knowledge Alpha", "Alpha provides routine advisory services."
        )
        owner_b, website_b = await published_site(
            session, "Knowledge Beta", "Beta provides unrelated bakery services."
        )
        indexer = KnowledgeIndexService(session, storage, settings, embeddings)
        for website in (website_a, website_b):
            initial = await indexer.request_for_published_website(
                website,
                website.published_version_id,
                f"knowledge-initial-{website.id}",
            )
            initial_event = await session.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_id == initial.id,
                    OutboxEvent.event_type == "chatbot.index_requested",
                )
            )
            assert initial_event is not None
            assert (await indexer.process_outbox_event(initial_event.id)).state == "PUBLISHED"

        sources = KnowledgeSourceService(session, storage, settings)
        source_a = await sources.create(
            website_id=website_a.id,
            owner_user_id=owner_a.id,
            filename="../../alpha-policy.txt",
            content_type="text/plain",
            data=b"The alpha-only warranty lasts exactly seven years.",
            correlation_id="knowledge-alpha-upload",
        )
        source_b = await sources.create(
            website_id=website_b.id,
            owner_user_id=owner_b.id,
            filename="beta-guide.md",
            content_type="text/markdown",
            data=b"The beta-only wholesale minimum is ninety loaves.",
            correlation_id="knowledge-beta-upload",
        )
        await session.flush()

        for source in (source_a, source_b):
            source_event = await session.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_id == source.id,
                    OutboxEvent.event_type == "knowledge.source_ingest_requested",
                )
            )
            assert source_event is not None
            assert (await sources.process_outbox_event(source_event.id)).state == "PUBLISHED"
            assert source.status == "READY"

        active_indexes: dict[object, ChatbotKnowledgeIndex] = {}
        for website in (website_a, website_b):
            requested = await session.scalar(
                select(ChatbotKnowledgeIndex).where(
                    ChatbotKnowledgeIndex.website_id == website.id,
                    ChatbotKnowledgeIndex.state == "REQUESTED",
                )
            )
            assert requested is not None
            index_event = await session.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_id == requested.id,
                    OutboxEvent.event_type == "chatbot.index_requested",
                )
            )
            assert index_event is not None
            assert (await indexer.process_outbox_event(index_event.id)).state == "PUBLISHED"
            active_indexes[website.id] = requested

        chunks_a = list(
            (
                await session.scalars(
                    select(ChatbotKnowledgeChunk).where(
                        ChatbotKnowledgeChunk.knowledge_index_id == active_indexes[website_a.id].id
                    )
                )
            ).all()
        )
        indexed_a = " ".join(chunk.content for chunk in chunks_a).casefold()
        assert "alpha-only warranty" in indexed_a
        assert "beta-only wholesale" not in indexed_a
        assert all(chunk.source_id in {None, source_a.id} for chunk in chunks_a)
        with pytest.raises(AuthProblem, match="Website not found"):
            await sources.list_for_owner(website_a.id, owner_b.id)

        chats = ChatbotService(session, storage, embeddings, settings=settings)
        conversation = await chats.start_conversation(website_a.id)
        reply = await chats.reply(
            website_id=website_a.id,
            conversation_id=conversation.conversation.id,
            access_token=conversation.access_token,
            message="How long is the alpha-only warranty?",
        )
        assert "seven years" in reply.answer.casefold()
        assert "beta-only" not in reply.answer.casefold()

        old_active_id = active_indexes[website_a.id].id
        failing = KnowledgeIndexService(session, storage, settings, FailingEmbeddings())
        failed_rebuild = await failing.request_rebuild(
            website_a, website_a.published_version_id, "knowledge-failed-rebuild"
        )
        during_rebuild = await chats.start_conversation(website_a.id)
        assert during_rebuild.conversation.website_id == website_a.id
        failed_event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == failed_rebuild.id)
        )
        assert failed_event is not None
        assert (await failing.process_outbox_event(failed_event.id)).state == "FAILED"
        chatbot = await session.scalar(select(Chatbot).where(Chatbot.website_id == website_a.id))
        assert chatbot is not None
        assert chatbot.state == "ACTIVE" and chatbot.active_index_id == old_active_id

        deleted = await sources.delete(
            source_a.id,
            website_a.id,
            owner_a.id,
            "knowledge-alpha-delete",
        )
        assert deleted.status == "DELETED"
        delete_event = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == source_a.id,
                OutboxEvent.event_type == "knowledge.source_delete_requested",
            )
        )
        assert delete_event is not None
        assert (await sources.process_outbox_event(delete_event.id)).state == "PUBLISHED"
        replacement = await session.scalar(
            select(ChatbotKnowledgeIndex)
            .where(
                ChatbotKnowledgeIndex.website_id == website_a.id,
                ChatbotKnowledgeIndex.state == "REQUESTED",
            )
            .order_by(ChatbotKnowledgeIndex.knowledge_generation.desc())
        )
        assert replacement is not None
        replacement_event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == replacement.id)
        )
        assert replacement_event is not None
        assert (await indexer.process_outbox_event(replacement_event.id)).state == "PUBLISHED"
        await session.flush()
        await session.refresh(chatbot)
        assert chatbot.active_index_id == replacement.id
        assert chatbot.active_index_id != old_active_id
        assert (
            await session.scalar(
                select(func.count(ChatbotKnowledgeChunk.id)).where(
                    ChatbotKnowledgeChunk.knowledge_index_id == replacement.id,
                    ChatbotKnowledgeChunk.source_id == source_a.id,
                )
            )
            == 0
        )
        assert await session.get(KnowledgeSource, source_a.id) is not None
        await session.commit()
