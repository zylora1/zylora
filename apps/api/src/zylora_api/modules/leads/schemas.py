from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PublicLeadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=80)
    enquiry: str = Field(min_length=1, max_length=10_000)
    page_path: str | None = Field(default=None, max_length=1024, pattern=r"^/")
    consent: dict[str, Any] = Field(default_factory=dict)
    turnstile_token: str | None = Field(default=None, max_length=2048)


class PublicLeadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source: str
    duplicate: bool
    whatsapp_notification_queued: bool


class LeadCreditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    balance: int
    policy: str


class LeadOwnerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source: str
    name: str
    email: EmailStr | None
    phone: str | None
    enquiry: str
    page_path: str | None
    status: str
    captured_at: str


class LeadCreditPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: str = Field(pattern=r"^(ALLOW_DEBT|REJECT_NEW)$")


class LeadCreditAdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    delta: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=1, max_length=240)


class LeadCreditAdjustmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    delta: int
    resulting_balance: int
    entry_type: str
