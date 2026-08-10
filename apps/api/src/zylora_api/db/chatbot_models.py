from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from zylora_api.db.base import Base


class Chatbot(Base):
    __tablename__ = "chatbots"
    __table_args__ = (
        CheckConstraint(
            "state IN ('REQUESTED','INDEXING','ACTIVE','FAILED','DISABLED')",
            name="ck_chatbots_state",
        ),
        UniqueConstraint("website_id", name="uq_chatbots_website"),
        UniqueConstraint("public_id", name="uq_chatbots_public_id"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="RESTRICT"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    public_id: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="REQUESTED")
    active_index_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chatbot_knowledge_indexes.id", ondelete="RESTRICT")
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatbotKnowledgeIndex(Base):
    __tablename__ = "chatbot_knowledge_indexes"
    __table_args__ = (
        CheckConstraint(
            (
                "state IN ('REQUESTED','EXTRACTING','EMBEDDING','BUILDING','VALIDATING',"
                "'ACTIVE','SUPERSEDED','FAILED','DELETED')"
            ),
            name="ck_chatbot_knowledge_indexes_state",
        ),
        UniqueConstraint(
            "website_id", "website_version_id", name="uq_chatbot_index_website_version"
        ),
        Index(
            "uq_chatbot_active_index_website",
            "website_id",
            unique=True,
            postgresql_where=text("state = 'ACTIVE'"),
        ),
        Index("ix_chatbot_indexes_website_state", "website_id", "state", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    chatbot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chatbots.id", ondelete="RESTRICT"), nullable=False
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="RESTRICT"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    website_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("website_versions.id", ondelete="RESTRICT"), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    chunker_version: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_key: Mapped[str | None] = mapped_column(String(1024))
    artifact_checksum: Mapped[str | None] = mapped_column(String(64))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    state: Mapped[str] = mapped_column(String(24), nullable=False, server_default="REQUESTED")
    failure_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatbotKnowledgeChunk(Base):
    __tablename__ = "chatbot_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("knowledge_index_id", "chunk_key", name="uq_chatbot_chunks_key"),
        UniqueConstraint("knowledge_index_id", "faiss_id", name="uq_chatbot_chunks_faiss_id"),
        Index("ix_chatbot_chunks_index", "knowledge_index_id", "faiss_id"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    knowledge_index_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chatbot_knowledge_indexes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chunk_key: Mapped[str] = mapped_column(String(120), nullable=False)
    source_page_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_component_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    faiss_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        CheckConstraint(
            "state IN ('OPEN','CLOSED','ARCHIVED')", name="ck_chat_conversations_state"
        ),
        Index("ix_chat_conversations_website_created", "website_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    chatbot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chatbots.id", ondelete="RESTRICT"), nullable=False
    )
    website_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("websites.id", ondelete="RESTRICT"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    access_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="OPEN")
    consent: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    lead_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="RESTRICT")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('USER','ASSISTANT','SYSTEM')", name="ck_chat_messages_role"),
        UniqueConstraint("conversation_id", "sequence", name="uq_chat_messages_sequence"),
        Index("ix_chat_messages_conversation", "conversation_id", "sequence"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
