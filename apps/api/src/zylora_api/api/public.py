from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.auth_models import User
from zylora_api.db.deployment_models import Domain
from zylora_api.db.session import get_session
from zylora_api.db.website_models import Website
from zylora_api.modules.analytics.schemas import PublicPageViewRequest, PublicPageViewResponse
from zylora_api.modules.analytics.service import AnalyticsService
from zylora_api.modules.auth.challenge import ChallengeService
from zylora_api.modules.auth.http import (
    correlation_id,
    get_challenge_service,
    get_crypto,
    request_ip,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.chatbot.schemas import (
    ChatMessageRequest,
    ChatReplyResponse,
    ConversationResponse,
    ConversationStartRequest,
    PublicLeadRequest,
    PublicLeadResponse,
)
from zylora_api.modules.chatbot.service import ChatbotService
from zylora_api.modules.commerce.quotas import LeadService
from zylora_api.modules.publishing.runtime import publication_storage_for
from zylora_api.modules.templates.service import problem

router = APIRouter(prefix="/api/v1/public", tags=["public-chatbot-and-leads"])


@dataclass(frozen=True)
class PublicWebsite:
    website: Website
    hostname: str
    owner_country_code: str


def _idempotency_key(value: str | None) -> str:
    if not value or not 16 <= len(value) <= 160:
        raise problem(
            422,
            "idempotency_key_required",
            "Provide an Idempotency-Key between 16 and 160 characters.",
        )
    return value


async def resolve_public_website(request: Request, session: AsyncSession) -> PublicWebsite:
    hostname = (request.url.hostname or "").casefold()
    if not hostname:
        raise problem(404, "published_website_not_found", "Published Website not found.")
    domain = await session.scalar(
        select(Domain).where(
            Domain.hostname == hostname,
            Domain.is_active.is_(True),
            Domain.state.in_(("ACTIVE", "DEGRADED")),
        )
    )
    if not domain:
        raise problem(404, "published_website_not_found", "Published Website not found.")
    website = await session.scalar(
        select(Website).where(
            Website.id == domain.website_id,
            Website.status == "PUBLISHED",
            Website.active_deployment_id.is_not(None),
            Website.live_owner_user_id.is_not(None),
        )
    )
    if not website:
        raise problem(404, "published_website_not_found", "Published Website not found.")
    owner = await session.get(User, website.live_owner_user_id)
    if not owner or owner.account_type != "USER" or owner.status != "ACTIVE":
        raise problem(404, "published_website_not_found", "Published Website not found.")
    return PublicWebsite(
        website=website, hostname=hostname, owner_country_code=owner.billing_country_code
    )


async def _enforce_public_challenge(
    *,
    token: str | None,
    context: PublicWebsite,
    request: Request,
    settings: Settings,
    challenge: ChallengeService,
    action: str,
) -> None:
    await challenge.enforce(
        token,
        expected_action=action,
        expected_hostname=context.hostname,
        remote_ip=request_ip(request, settings),
        correlation_id=correlation_id(request),
    )


@router.post(
    "/analytics/page-views",
    response_model=PublicPageViewResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def capture_page_view(
    payload: PublicPageViewRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> PublicPageViewResponse:
    context = await resolve_public_website(request, session)
    result = await AnalyticsService(session).record(
        website_id=context.website.id,
        event_type="PAGE_VIEW",
        idempotency_key=payload.event_id,
        page_path=payload.page_path,
        session_hash=crypto.digest(
            payload.session_id, purpose=f"analytics-session:{context.website.id}"
        ),
        visitor_hash=(
            crypto.digest(payload.visitor_id, purpose=f"analytics-visitor:{context.website.id}")
            if payload.visitor_id
            else None
        ),
    )
    await session.commit()
    return PublicPageViewResponse(accepted=True, duplicate=result.duplicate)


@router.post("/leads", response_model=PublicLeadResponse, status_code=status.HTTP_201_CREATED)
async def capture_form_lead(
    payload: PublicLeadRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PublicLeadResponse:
    context = await resolve_public_website(request, session)
    await _enforce_public_challenge(
        token=payload.turnstile_token,
        context=context,
        request=request,
        settings=settings,
        challenge=challenge,
        action="lead_submission",
    )
    result = await LeadService(session).capture(
        website_id=context.website.id,
        source="FORM",
        idempotency_key=_idempotency_key(idempotency_key),
        name=payload.name,
        email=str(payload.email) if payload.email else None,
        phone=payload.phone,
        enquiry=payload.enquiry,
        page_path=payload.page_path,
        consent=payload.consent,
        owner_country_code=context.owner_country_code,
        correlation_id=correlation_id(request),
    )
    await session.commit()
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    return PublicLeadResponse(
        id=result.lead.id,
        source=result.lead.source,
        duplicate=result.duplicate,
        whatsapp_notification_queued=result.lead.whatsapp_notification_queued,
    )


@router.post(
    "/chatbot/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_conversation(
    payload: ConversationStartRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationResponse:
    context = await resolve_public_website(request, session)
    created = await ChatbotService.from_settings(
        session, publication_storage_for(settings), settings
    ).start_conversation(context.website.id, payload.consent)
    await session.commit()
    return ConversationResponse(id=created.conversation.id, access_token=created.access_token)


@router.post("/chatbot/conversations/{conversation_id}/messages", response_model=ChatReplyResponse)
async def chat_message(
    conversation_id: UUID,
    payload: ChatMessageRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatReplyResponse:
    context = await resolve_public_website(request, session)
    reply = await ChatbotService.from_settings(
        session, publication_storage_for(settings), settings
    ).reply(
        website_id=context.website.id,
        conversation_id=conversation_id,
        access_token=payload.access_token,
        message=payload.message,
    )
    await session.commit()
    return ChatReplyResponse(
        conversation_id=reply.conversation.id,
        answer=reply.answer,
        source_paths=reply.source_paths,
    )


@router.post(
    "/chatbot/conversations/{conversation_id}/leads",
    response_model=PublicLeadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def capture_chatbot_lead(
    conversation_id: UUID,
    payload: PublicLeadRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PublicLeadResponse:
    context = await resolve_public_website(request, session)
    await _enforce_public_challenge(
        token=payload.turnstile_token,
        context=context,
        request=request,
        settings=settings,
        challenge=challenge,
        action="lead_submission",
    )
    access_token = request.headers.get("X-Zylora-Conversation-Token", "")
    result = await ChatbotService.from_settings(
        session, publication_storage_for(settings), settings
    ).capture_conversation_lead(
        website_id=context.website.id,
        conversation_id=conversation_id,
        access_token=access_token,
        idempotency_key=_idempotency_key(idempotency_key),
        name=payload.name,
        email=str(payload.email) if payload.email else None,
        phone=payload.phone,
        enquiry=payload.enquiry,
        owner_country_code=context.owner_country_code,
        correlation_id=correlation_id(request),
        page_path=payload.page_path,
        consent=payload.consent,
    )
    await session.commit()
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    return PublicLeadResponse(
        id=result.lead.id,
        source=result.lead.source,
        duplicate=result.duplicate,
        whatsapp_notification_queued=result.lead.whatsapp_notification_queued,
    )
