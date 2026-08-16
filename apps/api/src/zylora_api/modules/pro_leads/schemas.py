from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProLeadCreateRequest(Schema):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr = Field(max_length=320)
    website_type: str = Field(min_length=2, max_length=150)
    preferred_contact_time: str = Field(min_length=1, max_length=160)
    turnstile_token: str | None = Field(default=None, max_length=2048)
    company_website_url: str | None = Field(default=None, max_length=1024)

    @field_validator("name", "website_type", "preferred_contact_time")
    @classmethod
    def validate_non_whitespace(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or whitespace only.")
        return trimmed


class ProLeadResponse(Schema):
    id: UUID
    reference_id: str
    name: str
    email: str
    website_type: str
    preferred_contact_time: str
    status: Literal["PENDING", "CLOSED", "NOT_CLOSED"]
    amount_received: int | None = None
    submitted_at: datetime
    resolved_at: datetime | None = None


class ProLeadStatusUpdateRequest(Schema):
    status: Literal["CLOSED", "NOT_CLOSED"]
    amount_received: int | None = Field(default=None, ge=0)

    @field_validator("amount_received", mode="after")
    @classmethod
    def validate_closed_amount(cls, value: int | None, info: Any) -> int | None:
        return value


class ProLeadSummaryResponse(Schema):
    total_pro_leads: int = 0
    closed: int = 0
    not_closed: int = 0
    pending: int = 0
    amount_received: int = 0


class ProLeadListResponse(Schema):
    items: list[ProLeadResponse]
    summary: ProLeadSummaryResponse
