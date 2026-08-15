from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import faiss
import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.core.config import Settings
from zylora_api.db.chatbot_models import (
    Chatbot,
    ChatbotKnowledgeChunk,
    ChatbotKnowledgeIndex,
)
from zylora_api.db.knowledge_models import KnowledgeSource
from zylora_api.db.models import OutboxEvent
from zylora_api.db.website_models import Website, WebsiteVersion
from zylora_api.modules.chatbot.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
    OpenAIEmbeddingProvider,
)
from zylora_api.modules.publishing.service import DeploymentService
from zylora_api.modules.templates.service import problem
from zylora_api.storage.base import ObjectStorage

logger = logging.getLogger("zylora.chatbot.index")

CHUNKER_VERSION = "website-document-sections-v2"
TOKEN_PATTERN = re.compile(r"\S+")


@dataclass(frozen=True)
class ExtractedChunk:
    page_path: str
    component_path: str
    content: str
    source_id: UUID | None = None
    source_type: str = "WEBSITE"
    source_title: str = "Website"
    source_location: dict[str, Any] | None = None


class FaissIndexCodec:
    @staticmethod
    def build(vectors: list[list[float]]) -> bytes:
        if not vectors or not vectors[0]:
            raise ValueError("FAISS requires nonempty vectors")
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
            raise ValueError("FAISS vector matrix is invalid")
        if not np.isfinite(matrix).all():
            raise ValueError("FAISS vectors must be finite")
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(int(matrix.shape[1]))
        index.add(matrix)
        return bytes(faiss.serialize_index(index))

    @staticmethod
    def search_with_scores(data: bytes, vector: list[float], limit: int) -> list[tuple[int, float]]:
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        index = faiss.deserialize_index(np.frombuffer(data, dtype=np.uint8))
        query = np.asarray([vector], dtype=np.float32)
        if query.ndim != 2 or query.shape[1] != index.d:
            raise ValueError("query vector dimension does not match index")
        if not np.isfinite(query).all():
            raise ValueError("query vector must be finite")
        faiss.normalize_L2(query)
        scores, identifiers = index.search(query, min(limit, index.ntotal))
        return [
            (int(identifier), float(score))
            for identifier, score in zip(identifiers[0], scores[0], strict=True)
            if int(identifier) >= 0
        ]

    @staticmethod
    def search(data: bytes, vector: list[float], limit: int) -> list[int]:
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        index = faiss.deserialize_index(np.frombuffer(data, dtype=np.uint8))
        query = np.asarray([vector], dtype=np.float32)
        if query.shape[1] != index.d:
            raise ValueError("query vector dimension does not match index")
        faiss.normalize_L2(query)
        _, identifiers = index.search(query, min(limit, index.ntotal))
        return [int(value) for value in identifiers[0] if int(value) >= 0]


class KnowledgeIndexService:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage,
        settings: Settings,
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings
        self.embeddings = embeddings or OpenAIEmbeddingProvider(settings)

    async def request_for_published_website(
        self, website: Website, version_id: UUID, correlation_id: str
    ) -> ChatbotKnowledgeIndex:
        chatbot = await self.session.scalar(
            select(Chatbot).where(Chatbot.website_id == website.id).with_for_update()
        )
        if not chatbot:
            chatbot = Chatbot(
                website_id=website.id,
                owner_user_id=website.owner_user_id,
                public_id=secrets.token_urlsafe(24),
                state="REQUESTED",
            )
            self.session.add(chatbot)
            await self.session.flush()
        elif chatbot.owner_user_id != website.owner_user_id:
            if chatbot.active_index_id is not None:
                raise problem(409, "chatbot_owner_mismatch", "Chatbot ownership is inconsistent.")
            chatbot.owner_user_id = website.owner_user_id
            chatbot.public_id = secrets.token_urlsafe(24)
            chatbot.state = "REQUESTED"
            chatbot.version += 1
        existing = await self.session.scalar(
            select(ChatbotKnowledgeIndex).where(
                ChatbotKnowledgeIndex.website_id == website.id,
                ChatbotKnowledgeIndex.website_version_id == version_id,
                ChatbotKnowledgeIndex.knowledge_generation == 1,
            )
        )
        if existing:
            return existing
        knowledge_index = ChatbotKnowledgeIndex(
            chatbot_id=chatbot.id,
            website_id=website.id,
            owner_user_id=website.owner_user_id,
            website_version_id=version_id,
            embedding_model=self.settings.chatbot_embedding_model,
            knowledge_generation=1,
            embedding_dimension=self.settings.chatbot_embedding_dimension,
            chunker_version=CHUNKER_VERSION,
            state="REQUESTED",
        )
        chatbot.state = "INDEXING"
        chatbot.version += 1
        self.session.add(knowledge_index)
        await self.session.flush()
        self.session.add(
            OutboxEvent(
                aggregate_type="CHATBOT_KNOWLEDGE_INDEX",
                aggregate_id=knowledge_index.id,
                event_type="chatbot.index_requested",
                payload={"knowledge_index_id": str(knowledge_index.id)},
                correlation_id=correlation_id,
            )
        )
        return knowledge_index

    async def request_rebuild(
        self, website: Website, version_id: UUID, correlation_id: str
    ) -> ChatbotKnowledgeIndex:
        chatbot = await self.session.scalar(
            select(Chatbot).where(Chatbot.website_id == website.id).with_for_update()
        )
        if not chatbot or chatbot.owner_user_id != website.owner_user_id:
            raise problem(409, "chatbot_owner_mismatch", "Chatbot ownership is inconsistent.")
        generation = (
            int(
                await self.session.scalar(
                    select(
                        func.coalesce(func.max(ChatbotKnowledgeIndex.knowledge_generation), 0)
                    ).where(
                        ChatbotKnowledgeIndex.website_id == website.id,
                        ChatbotKnowledgeIndex.website_version_id == version_id,
                    )
                )
                or 0
            )
            + 1
        )
        knowledge_index = ChatbotKnowledgeIndex(
            chatbot_id=chatbot.id,
            website_id=website.id,
            owner_user_id=website.owner_user_id,
            website_version_id=version_id,
            knowledge_generation=generation,
            embedding_model=self.settings.chatbot_embedding_model,
            embedding_dimension=self.settings.chatbot_embedding_dimension,
            chunker_version=CHUNKER_VERSION,
            state="REQUESTED",
        )
        chatbot.state = "INDEXING"
        chatbot.version += 1
        self.session.add(knowledge_index)
        await self.session.flush()
        self.session.add(
            OutboxEvent(
                aggregate_type="CHATBOT_KNOWLEDGE_INDEX",
                aggregate_id=knowledge_index.id,
                event_type="chatbot.index_requested",
                payload={"knowledge_index_id": str(knowledge_index.id)},
                correlation_id=correlation_id,
            )
        )
        return knowledge_index

    async def build(self, knowledge_index_id: UUID) -> ChatbotKnowledgeIndex:
        index = await self.session.scalar(
            select(ChatbotKnowledgeIndex)
            .where(ChatbotKnowledgeIndex.id == knowledge_index_id)
            .with_for_update()
        )
        if not index:
            raise problem(404, "knowledge_index_not_found", "Knowledge index not found.")
        if index.state in {"ACTIVE", "SUPERSEDED", "DELETED"}:
            return index
        chatbot = await self.session.scalar(
            select(Chatbot).where(Chatbot.id == index.chatbot_id).with_for_update()
        )
        website = await self.session.scalar(
            select(Website).where(Website.id == index.website_id).with_for_update()
        )
        version = await self.session.get(WebsiteVersion, index.website_version_id)
        if (
            not chatbot
            or not website
            or not version
            or chatbot.website_id != index.website_id
            or chatbot.owner_user_id != index.owner_user_id
            or website.owner_user_id != index.owner_user_id
            or website.status != "PUBLISHED"
            or website.published_version_id != index.website_version_id
        ):
            index.state = "FAILED"
            index.failure_code = "published_source_unavailable"
            if chatbot:
                chatbot.state = "FAILED" if chatbot.active_index_id is None else "ACTIVE"
                chatbot.version += 1
            return index
        active = (
            await self.session.get(ChatbotKnowledgeIndex, chatbot.active_index_id)
            if chatbot.active_index_id
            else None
        )
        if (
            active
            and active.id != index.id
            and active.knowledge_generation > index.knowledge_generation
        ):
            index.state = "SUPERSEDED"
            return index
        logger.info(
            "chatbot_index_started",
            extra={
                "website_id": str(index.website_id),
                "index_id": str(index.id),
                "event_type": "knowledge.index_started",
                "outcome": "building",
            },
        )
        try:
            chatbot.state = "INDEXING"
            index.state = "EXTRACTING"
            chunks = self._extract(version, self.settings.chatbot_chunk_characters)
            sources = list(
                (
                    await self.session.scalars(
                        select(KnowledgeSource).where(
                            KnowledgeSource.website_id == index.website_id,
                            KnowledgeSource.owner_user_id == index.owner_user_id,
                            KnowledgeSource.status == "READY",
                            KnowledgeSource.extracted_storage_key.is_not(None),
                        )
                    )
                ).all()
            )
            for source in sources:
                chunks.extend(self._extract_source(source))
            if not chunks:
                raise ValueError("published source has no indexable text")
            index.state = "EMBEDDING"
            vectors = await self.embeddings.embed([item.content for item in chunks])
            if len(vectors) != len(chunks) or not vectors or not vectors[0]:
                raise ValueError("embedding count is invalid")
            dimension = len(vectors[0])
            if any(len(item) != dimension for item in vectors):
                raise ValueError("embedding dimensions differ")
            if (
                self.embeddings.model != self.settings.chatbot_embedding_model
                or dimension != self.settings.chatbot_embedding_dimension
            ):
                raise ValueError("embedding metadata is incompatible with configured index")
            index.embedding_model = self.embeddings.model
            index.embedding_dimension = dimension
            index.state = "BUILDING"
            artifact = FaissIndexCodec.build(vectors)
            checksum = hashlib.sha256(artifact).hexdigest()
            object_key = (
                f"faiss/{index.website_id}/{index.owner_user_id}/{index.id}/{checksum}.index"
            )
            self.storage.put_bytes(object_key, artifact, "application/vnd.faiss")
            index.artifact_key = object_key
            index.artifact_checksum = checksum
            index.manifest = {
                "website_id": str(index.website_id),
                "owner_user_id": str(index.owner_user_id),
                "website_version_id": str(index.website_version_id),
                "embedding_model": index.embedding_model,
                "knowledge_generation": index.knowledge_generation,
                "embedding_dimension": dimension,
                "chunker_version": CHUNKER_VERSION,
                "chunk_count": len(chunks),
                "source_versions": [
                    {"source_id": str(source.id), "version": source.version} for source in sources
                ],
                "artifact_checksum": checksum,
            }
            index.state = "VALIDATING"
            if not FaissIndexCodec.search(artifact, vectors[0], 1):
                raise ValueError("FAISS smoke search returned no result")
            for faiss_id, chunk in enumerate(chunks):
                self.session.add(
                    ChatbotKnowledgeChunk(
                        knowledge_index_id=index.id,
                        chunk_key=f"chunk-{faiss_id}",
                        source_page_path=chunk.page_path,
                        source_component_path=chunk.component_path,
                        content=chunk.content,
                        token_count=len(TOKEN_PATTERN.findall(chunk.content)),
                        source_id=chunk.source_id,
                        source_type=chunk.source_type,
                        source_title=chunk.source_title,
                        source_location=chunk.source_location or {},
                        checksum=hashlib.sha256(chunk.content.encode()).hexdigest(),
                        faiss_id=faiss_id,
                    )
                )
            prior = await self.session.scalar(
                select(ChatbotKnowledgeIndex)
                .where(
                    ChatbotKnowledgeIndex.website_id == index.website_id,
                    ChatbotKnowledgeIndex.state == "ACTIVE",
                )
                .with_for_update()
            )
            if prior and prior.id != index.id:
                prior.state = "SUPERSEDED"
            index.state = "ACTIVE"
            index.activated_at = datetime.now(UTC)
            index.failure_code = None
            chatbot.active_index_id = index.id
            chatbot.state = "ACTIVE"
            chatbot.version += 1
            for source in sources:
                source.indexed_at = index.activated_at
            logger.info(
                "chatbot_index_completed",
                extra={
                    "website_id": str(index.website_id),
                    "index_id": str(index.id),
                    "event_type": "knowledge.index_completed",
                    "artifact_bytes": len(artifact),
                    "outcome": "active",
                },
            )
            return index
        except (EmbeddingProviderError, OSError, RuntimeError, ValueError):
            index.state = "FAILED"
            index.failure_code = "knowledge_index_build_failed"
            chatbot.state = "FAILED" if chatbot.active_index_id is None else "ACTIVE"
            chatbot.version += 1
            logger.warning(
                "chatbot_index_failed",
                extra={
                    "website_id": str(index.website_id),
                    "index_id": str(index.id),
                    "event_type": "knowledge.index_failed",
                    "outcome": "failed",
                    "safe_error_code": index.failure_code,
                },
            )
            return index

    async def process_outbox_event(self, event_id: UUID) -> OutboxEvent:
        event = await self.session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if not event:
            raise problem(404, "chatbot_event_not_found", "Chatbot job not found.")
        if event.state == "PUBLISHED":
            return event
        event.attempts += 1
        try:
            if event.event_type == "chatbot.index_requested":
                built = await self.build(UUID(str(event.payload["knowledge_index_id"])))
                event.state = "PUBLISHED" if built.state == "ACTIVE" else "FAILED"
                event.last_error_code = built.failure_code
            elif event.event_type == "chatbot.cleanup_requested":
                artifact_key = event.payload.get("artifact_key")
                if isinstance(artifact_key, str) and artifact_key:
                    self.storage.delete(artifact_key)
                event.state = "PUBLISHED"
                event.last_error_code = None
            else:
                raise ValueError("unsupported chatbot event")
            if event.state == "PUBLISHED":
                event.published_at = datetime.now(UTC)
        except (KeyError, ValueError):
            event.state = "FAILED"
            event.last_error_code = "chatbot_event_failed"
        finally:
            event.lease_owner = None
            event.leased_until = None
        return event

    def _extract_source(self, source: KnowledgeSource) -> list[ExtractedChunk]:
        if not source.extracted_storage_key:
            return []
        payload = json.loads(self.storage.get_bytes(source.extracted_storage_key))
        if (
            not isinstance(payload, dict)
            or payload.get("source_id") != str(source.id)
            or payload.get("source_version") != source.version
        ):
            raise ValueError("extracted source metadata is invalid")
        sections = payload.get("sections")
        if not isinstance(sections, list):
            raise ValueError("extracted source sections are invalid")
        result: list[ExtractedChunk] = []
        for position, section in enumerate(sections):
            if not isinstance(section, dict) or not isinstance(section.get("text"), str):
                raise ValueError("extracted source section is invalid")
            location = {
                key: value
                for key, value in {
                    "page_number": section.get("page_number"),
                    "heading": section.get("heading"),
                }.items()
                if value is not None
            }
            result.extend(
                self._split(
                    f"document/{source.safe_display_name}",
                    f"sections[{position}]",
                    section["text"],
                    source_id=source.id,
                    source_type=source.source_type,
                    source_title=source.safe_display_name,
                    source_location=location,
                )
            )
        return result

    @staticmethod
    def _extract(version: WebsiteVersion, chunk_characters: int = 900) -> list[ExtractedChunk]:
        pages = DeploymentService._snapshot_pages(version)
        extracted: list[ExtractedChunk] = []
        for page in pages:
            page_path = str(page.get("path") or "/")
            name = str(page.get("name") or page.get("label") or "")
            if name:
                extracted.extend(
                    KnowledgeIndexService._split(
                        page_path,
                        "page.name",
                        name,
                        source_title=name,
                        limit=chunk_characters,
                    )
                )
            components = page.get("components")
            if isinstance(components, list):
                for position, component in enumerate(components):
                    if isinstance(component, dict):
                        text = KnowledgeIndexService._component_text(component)
                        if text:
                            extracted.extend(
                                KnowledgeIndexService._split(
                                    page_path,
                                    f"components[{position}]",
                                    text,
                                    source_title=name or "Website",
                                    limit=chunk_characters,
                                )
                            )
        return extracted

    @staticmethod
    def _component_text(component: dict[str, Any]) -> str:
        values: list[str] = []

        def visit(value: Any) -> None:
            if isinstance(value, str):
                normalized = " ".join(value.split())
                if normalized and not normalized.startswith(("http://", "https://", "/")):
                    values.append(normalized)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
            elif isinstance(value, dict):
                for item in value.values():
                    visit(item)

        props = component.get("props")
        if isinstance(props, dict):
            visit(props)
        return " ".join(dict.fromkeys(values))

    @staticmethod
    def _split(
        page_path: str,
        component_path: str,
        content: str,
        *,
        source_id: UUID | None = None,
        source_type: str = "WEBSITE",
        source_title: str = "Website",
        source_location: dict[str, Any] | None = None,
        limit: int = 900,
    ) -> list[ExtractedChunk]:
        normalized = " ".join(content.split())

        def chunk(value: str) -> ExtractedChunk:
            return ExtractedChunk(
                page_path=page_path,
                component_path=component_path,
                content=value,
                source_id=source_id,
                source_type=source_type,
                source_title=source_title,
                source_location=source_location,
            )

        if len(normalized) <= limit:
            return [chunk(normalized)]
        chunks: list[ExtractedChunk] = []
        current: list[str] = []
        size = 0
        for word in normalized.split():
            if current and size + len(word) + 1 > limit:
                chunks.append(chunk(" ".join(current)))
                current = []
                size = 0
            current.append(word)
            size += len(word) + (1 if size else 0)
        if current:
            chunks.append(chunk(" ".join(current)))
        return chunks
