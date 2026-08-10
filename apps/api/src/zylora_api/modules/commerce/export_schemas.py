from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field
from zylora_api.modules.commerce.schemas import MoneyResponse, Schema


class ExportPriceConfigureRequest(Schema):
    currency: Literal["INR", "USD"]
    amount_minor: int = Field(gt=0)
    active: bool = True


class ExportPriceResponse(Schema):
    id: UUID
    currency: Literal["INR", "USD"]
    amount_minor: int
    active: bool
    version: int
    effective_at: datetime
    created_at: datetime


class ExportPurchaseResponse(Schema):
    id: UUID
    website_id: UUID
    website_version_id: UUID
    status: Literal[
        "CREATED", "PAYMENT_PENDING", "PAID", "GENERATING", "READY", "FAILED", "EXPIRED", "REFUNDED"
    ]
    price: MoneyResponse
    created_at: datetime
    paid_at: datetime | None
    ready_at: datetime | None
    expires_at: datetime | None
    failure_code: str | None = None


class ExportCheckoutResponse(Schema):
    purchase: ExportPurchaseResponse
    payment_id: UUID
    provider_available: bool
    detail: str


class ExportGenerationResponse(Schema):
    purchase: ExportPurchaseResponse
    queued: bool
