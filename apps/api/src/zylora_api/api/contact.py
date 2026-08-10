from __future__ import annotations

import hashlib
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.session import get_session
from zylora_api.modules.auth.challenge import ChallengeService
from zylora_api.modules.auth.http import (
    correlation_id,
    get_challenge_service,
    get_crypto,
    request_ip,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.notifications.email import TransactionalEmailService
from zylora_api.modules.templates.service import problem

router = APIRouter(prefix="/api/v1/public", tags=["public-contact"])


class ContactAcceptedResponse(BaseModel):
    status: Literal["accepted"]
    id: UUID


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    message: str = Field(min_length=20, max_length=5000)
    turnstile_token: str | None = Field(default=None, max_length=2048)


@router.post(
    "/contact", response_model=ContactAcceptedResponse, status_code=status.HTTP_202_ACCEPTED
)
async def submit_contact(
    payload: ContactRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
) -> ContactAcceptedResponse:
    if not settings.contact_recipient_email:
        raise problem(503, "contact_unavailable", "Contact is temporarily unavailable.")
    await challenge.enforce(
        payload.turnstile_token,
        expected_action="contact",
        remote_ip=request_ip(request, settings),
        correlation_id=correlation_id(request),
    )
    digest = hashlib.sha256(
        f"{payload.email.casefold()}:{payload.message.strip()}".encode()
    ).hexdigest()
    email = await TransactionalEmailService(session, crypto).queue(
        recipient_email=settings.contact_recipient_email,
        recipient_user_id=None,
        kind="CONTACT_SUBMISSION",
        resource_type="public_contact",
        resource_id=None,
        idempotency_key=f"contact:{digest}",
        subject="New Zylora contact request",
        body=f"From: {payload.name.strip()} <{payload.email}>\n\n{payload.message.strip()}",
        correlation_id=correlation_id(request),
    )
    await session.commit()
    return ContactAcceptedResponse(status="accepted", id=email.id)
