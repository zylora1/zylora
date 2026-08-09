from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


EntitlementValue = bool | int | str


class MoneyResponse(Schema):
    amount_minor: int = Field(ge=0)
    currency: Literal["INR", "USD"]


class PlanResponse(Schema):
    id: UUID
    code: Literal["FREE", "BASIC", "GROWTH", "BUSINESS"]
    name: str
    description: str
    slot: int = Field(ge=1, le=4)
    most_popular: bool
    price: MoneyResponse
    interval: Literal["MONTHLY"]
    entitlements: dict[str, EntitlementValue]


class PlanListResponse(Schema):
    region: Literal["INDIA", "INTERNATIONAL"]
    country_code: str = Field(min_length=2, max_length=2)
    currency: Literal["INR", "USD"]
    interval: Literal["MONTHLY"]
    items: list[PlanResponse]


class EligibilityReasonResponse(Schema):
    code: str
    detail: str
    current: int | str | bool | None = None
    allowed: int | str | bool | None = None


class PlanEligibilityResponse(Schema):
    plan: PlanResponse
    eligible: bool
    reasons: list[EligibilityReasonResponse]
    is_current_plan: bool


class PublishEvaluationResponse(Schema):
    website_id: UUID
    page_count: int
    domain_type: Literal["ZYLORA_SUBDOMAIN", "CUSTOM"]
    current_plan_code: str
    reuse_existing_subscription: bool
    can_request_publish: bool
    status: Literal["ELIGIBLE", "UPGRADE_REQUIRED", "INELIGIBLE"]
    recommended_plan_code: str | None
    plans: list[PlanEligibilityResponse]


class PublishRequest(Schema):
    domain_type: Literal["ZYLORA_SUBDOMAIN", "CUSTOM"] = "ZYLORA_SUBDOMAIN"


class PublishCommandResponse(Schema):
    website_id: UUID
    status: Literal["PUBLISHING"]
    plan_code: str
    reused_existing_subscription: bool
    message: str


class UnpublishCommandResponse(Schema):
    website_id: UUID
    status: str
    message: str


class SubscriptionResponse(Schema):
    plan_code: str
    state: str
    is_paid: bool
    price: MoneyResponse
    interval: Literal["MONTHLY"]
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    entitlements: dict[str, EntitlementValue]


class CheckoutRequest(Schema):
    plan_id: UUID


class CheckoutResponse(Schema):
    payment_id: UUID
    status: str
    price: MoneyResponse
    provider_available: bool
    detail: str


class CancelSubscriptionResponse(Schema):
    plan_code: str
    state: str
    cancel_at_period_end: bool
    current_period_end: datetime
    message: str
