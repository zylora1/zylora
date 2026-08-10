from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.chatbot_models import (
    Chatbot,
    ChatbotKnowledgeChunk,
    ChatbotKnowledgeIndex,
    ChatConversation,
    ChatMessage,
)
from zylora_api.db.website_models import Website
from zylora_api.modules.analytics.service import AnalyticsService
from zylora_api.modules.chatbot.embeddings import EmbeddingProvider, OpenAIEmbeddingProvider
from zylora_api.modules.chatbot.indexing import FaissIndexCodec
from zylora_api.modules.commerce.quotas import LeadCaptureResult, LeadService
from zylora_api.modules.templates.service import problem
from zylora_api.storage.base import ObjectStorage


@dataclass(frozen=True)
class ConversationSession:
    conversation: ChatConversation
    access_token: str


@dataclass(frozen=True)
class ChatReply:
    conversation: ChatConversation
    answer: str
    source_paths: list[str]


class ChatbotService:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage,
        embeddings: EmbeddingProvider,
    ) -> None:
        self.session = session
        self.storage = storage
        self.embeddings = embeddings

    @classmethod
    def from_settings(
        cls, session: AsyncSession, storage: ObjectStorage, settings: Any
    ) -> ChatbotService:
        return cls(session, storage, OpenAIEmbeddingProvider(settings))

    async def start_conversation(
        self, website_id: UUID, consent: dict[str, Any] | None = None
    ) -> ConversationSession:
        chatbot, _ = await self._active_chatbot(website_id)
        token = secrets.token_urlsafe(32)
        conversation = ChatConversation(
            chatbot_id=chatbot.id,
            website_id=website_id,
            owner_user_id=chatbot.owner_user_id,
            access_token_hash=hashlib.sha256(token.encode()).hexdigest(),
            consent=consent or {},
        )
        self.session.add(conversation)
        await self.session.flush()
        await AnalyticsService(self.session).record(
            website_id=website_id,
            owner_user_id=chatbot.owner_user_id,
            event_type="CHATBOT_CONVERSATION_STARTED",
            idempotency_key=f"chatbot-conversation:{conversation.id}",
            properties={},
        )
        return ConversationSession(conversation=conversation, access_token=token)

    async def reply(
        self,
        *,
        website_id: UUID,
        conversation_id: UUID,
        access_token: str,
        message: str,
    ) -> ChatReply:
        normalized = " ".join(message.split())
        if not normalized or len(normalized) > 4000:
            raise problem(422, "invalid_chat_message", "Enter a message up to 4,000 characters.")
        conversation = await self._conversation(website_id, conversation_id, access_token)
        chatbot, index = await self._active_chatbot(website_id)
        if (
            conversation.chatbot_id != chatbot.id
            or conversation.owner_user_id != chatbot.owner_user_id
        ):
            raise problem(404, "chat_conversation_not_found", "Conversation not found.")
        if not index.artifact_key or not index.artifact_checksum:
            raise problem(503, "chatbot_unavailable", "The Website chatbot is not ready.")
        try:
            artifact = self.storage.get_bytes(index.artifact_key)
        except (OSError, RuntimeError, KeyError, ValueError) as error:
            raise problem(
                503, "chatbot_unavailable", "The Website chatbot is not ready."
            ) from error
        if hashlib.sha256(artifact).hexdigest() != index.artifact_checksum:
            raise problem(503, "chatbot_index_invalid", "The Website chatbot is unavailable.")
        query_vectors = await self.embeddings.embed([normalized])
        if len(query_vectors) != 1:
            raise problem(503, "chatbot_unavailable", "The Website chatbot is unavailable.")
        try:
            faiss_ids = FaissIndexCodec.search(artifact, query_vectors[0], 4)
        except ValueError as error:
            raise problem(
                503, "chatbot_index_invalid", "The Website chatbot is unavailable."
            ) from error
        chunks = list(
            (
                await self.session.scalars(
                    select(ChatbotKnowledgeChunk).where(
                        ChatbotKnowledgeChunk.knowledge_index_id == index.id,
                        ChatbotKnowledgeChunk.faiss_id.in_(faiss_ids),
                    )
                )
            ).all()
        )
        by_faiss_id = {chunk.faiss_id: chunk for chunk in chunks}
        ordered = [by_faiss_id[item] for item in faiss_ids if item in by_faiss_id]
        if not ordered:
            answer = (
                "I could not find that information on this Website yet. "
                "Please contact the business directly."
            )
            source_paths: list[str] = []
        else:
            excerpts = [item.content for item in ordered[:2]]
            answer = " ".join(excerpts)
            source_paths = list(dict.fromkeys(item.source_page_path for item in ordered))
        next_sequence = int(
            (
                await self.session.scalar(
                    select(func.coalesce(func.max(ChatMessage.sequence), 0)).where(
                        ChatMessage.conversation_id == conversation.id
                    )
                )
            )
            or 0
        )
        retrieval = {
            "knowledge_index_id": str(index.id),
            "chunk_ids": [str(item.id) for item in ordered],
        }
        await AnalyticsService(self.session).record(
            website_id=website_id,
            owner_user_id=chatbot.owner_user_id,
            event_type="CHATBOT_MESSAGE",
            idempotency_key=f"chatbot-message:{conversation.id}:{next_sequence + 1}",
            properties={},
        )
        self.session.add_all(
            [
                ChatMessage(
                    conversation_id=conversation.id,
                    sequence=next_sequence + 1,
                    role="USER",
                    content=normalized,
                ),
                ChatMessage(
                    conversation_id=conversation.id,
                    sequence=next_sequence + 2,
                    role="ASSISTANT",
                    content=answer,
                    retrieval=retrieval,
                ),
            ]
        )
        return ChatReply(conversation=conversation, answer=answer, source_paths=source_paths)

    async def capture_conversation_lead(
        self,
        *,
        website_id: UUID,
        conversation_id: UUID,
        access_token: str,
        idempotency_key: str,
        name: str,
        email: str | None,
        phone: str | None,
        enquiry: str,
        owner_country_code: str,
        correlation_id: str,
        page_path: str | None,
        consent: dict[str, Any] | None,
    ) -> LeadCaptureResult:
        conversation = await self._conversation(website_id, conversation_id, access_token)
        result = await LeadService(self.session).capture(
            website_id=website_id,
            source="CHATBOT",
            source_reference_id=conversation.id,
            idempotency_key=idempotency_key,
            name=name,
            email=email,
            phone=phone,
            enquiry=enquiry,
            owner_country_code=owner_country_code,
            correlation_id=correlation_id,
            page_path=page_path,
            consent=consent,
        )
        conversation.lead_id = result.lead.id
        return result

    async def _active_chatbot(self, website_id: UUID) -> tuple[Chatbot, ChatbotKnowledgeIndex]:
        website = await self.session.scalar(
            select(Website).where(
                Website.id == website_id,
                Website.status == "PUBLISHED",
                Website.live_owner_user_id.is_not(None),
            )
        )
        if not website:
            raise problem(404, "published_website_not_found", "Published Website not found.")
        chatbot = await self.session.scalar(
            select(Chatbot).where(
                Chatbot.website_id == website_id,
                Chatbot.owner_user_id == website.live_owner_user_id,
                Chatbot.state == "ACTIVE",
                Chatbot.active_index_id.is_not(None),
            )
        )
        if not chatbot or not chatbot.active_index_id:
            raise problem(503, "chatbot_unavailable", "The Website chatbot is not ready.")
        index = await self.session.scalar(
            select(ChatbotKnowledgeIndex).where(
                ChatbotKnowledgeIndex.id == chatbot.active_index_id,
                ChatbotKnowledgeIndex.chatbot_id == chatbot.id,
                ChatbotKnowledgeIndex.website_id == website_id,
                ChatbotKnowledgeIndex.owner_user_id == website.live_owner_user_id,
                ChatbotKnowledgeIndex.website_version_id == website.published_version_id,
                ChatbotKnowledgeIndex.state == "ACTIVE",
            )
        )
        if not index:
            raise problem(503, "chatbot_unavailable", "The Website chatbot is not ready.")
        return chatbot, index

    async def _conversation(
        self, website_id: UUID, conversation_id: UUID, access_token: str
    ) -> ChatConversation:
        if not access_token or len(access_token) > 256:
            raise problem(404, "chat_conversation_not_found", "Conversation not found.")
        conversation = await self.session.scalar(
            select(ChatConversation)
            .where(
                ChatConversation.id == conversation_id,
                ChatConversation.website_id == website_id,
                ChatConversation.state == "OPEN",
            )
            .with_for_update()
        )
        candidate = hashlib.sha256(access_token.encode()).hexdigest()
        if not conversation or not hmac.compare_digest(conversation.access_token_hash, candidate):
            raise problem(404, "chat_conversation_not_found", "Conversation not found.")
        return conversation
