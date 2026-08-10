from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CampaignRequest(Schema):
    name: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20_000)
    audience_type: Literal[
        "ALL_USERS",
        "FREE_USERS",
        "PAID_USERS",
        "PLAN_USERS",
        "RECENT_USERS",
        "HAS_DRAFT",
        "NO_PUBLISHED_WEBSITE",
    ]
    audience_plan_code: Literal["FREE", "BASIC", "GROWTH", "BUSINESS"] | None = None


class CampaignResponse(Schema):
    id: UUID
    name: str
    subject: str
    state: str
    audience_type: str
    audience_plan_code: str | None
    audience_snapshot_count: int
    scheduled_at: datetime | None
    created_at: datetime
    accepted_count: int = 0
    failed_count: int = 0
    suppressed_count: int = 0
    unsubscribed_count: int = 0


class CampaignScheduleRequest(Schema):
    scheduled_at: datetime
    reason: str = Field(min_length=3, max_length=500)


class CampaignReasonRequest(Schema):
    reason: str = Field(min_length=3, max_length=500)


class AdministrativeEmailRequest(Schema):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20_000)
    reason: str = Field(min_length=3, max_length=500)


class UnsubscribeRequest(Schema):
    token: str = Field(min_length=20, max_length=200)
