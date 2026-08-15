from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent: dict[str, Any] = Field(default_factory=dict)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    access_token: str


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    access_token: str = Field(min_length=20, max_length=256)
    message: str = Field(min_length=1, max_length=4000)


class ChatReplyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    answer: str
    source_paths: list[str]
