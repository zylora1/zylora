from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr
from zylora_api.modules.commerce.schemas import Schema

TRANSFER_CONFIRMATION_VERSION = "OWNER_TRANSFER_V1"


class OwnershipTransferValidationRequest(Schema):
    recipient_email: EmailStr


class OwnershipTransferValidationResponse(Schema):
    website_id: UUID
    recipient_email: EmailStr
    eligible: bool
    requires_route_deactivation: bool


class OwnershipTransferRequest(Schema):
    recipient_email: EmailStr
    confirmation_version: Literal["OWNER_TRANSFER_V1"]


class OwnershipTransferResponse(Schema):
    id: UUID
    website_id: UUID
    sender_user_id: UUID
    recipient_user_id: UUID
    status: Literal["VALIDATED", "DEACTIVATING", "COMPLETED", "FAILED"]
    failure_code: str | None = None
    validated_at: datetime | None
    completed_at: datetime | None
