from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr
from zylora_api.modules.commerce.schemas import Schema


class OwnershipTransferRequest(Schema):
    recipient_email: EmailStr


class OwnershipTransferResponse(Schema):
    id: UUID
    website_id: UUID
    sender_user_id: UUID
    recipient_user_id: UUID
    status: str
    completed_at: datetime
