from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.chatbot_models import Chatbot, ChatbotKnowledgeIndex
from zylora_api.db.knowledge_models import KnowledgeSource
from zylora_api.db.session import get_session
from zylora_api.db.whatsapp_models import (
    WhatsAppNotification,
    WhatsAppNotificationSetting,
)
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.http import (
    RequestIdentity,
    correlation_id,
    get_crypto,
    get_user_identity,
    request_ip,
    require_csrf,
    require_json_origin,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.chatbot.service import ChatbotService
from zylora_api.modules.knowledge.service import KnowledgeSourceService
from zylora_api.modules.notifications.whatsapp import WhatsAppNotificationService
from zylora_api.modules.publishing.runtime import publication_storage_for
from zylora_api.modules.templates.service import problem
from zylora_api.modules.websites.service import WebsiteService

router = APIRouter(prefix="/api/v1/websites/{website_id}", tags=["chatbot-knowledge-whatsapp"])


class KnowledgeSourceResponse(BaseModel):
    id: UUID
    type: str
    display_name: str
    mime_type: str
    byte_size: int
    status: str
    failure_code: str | None
    failure_message: str | None
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeOverviewResponse(BaseModel):
    chatbot_status: str
    chatbot_enabled: bool
    active_index_id: UUID | None
    knowledge_generation: int | None
    source_limit: int
    last_indexed_at: datetime | None
    source_count: int
    sources: list[KnowledgeSourceResponse]


class ChatbotSettingRequest(BaseModel):
    enabled: bool


class ChatbotPreviewRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatbotPreviewResponse(BaseModel):
    answer: str
    sources: list[str]


class WhatsAppSettingRequest(BaseModel):
    phone_number: str | None = Field(default=None, min_length=3, max_length=80)
    country_code: str = Field(min_length=2, max_length=2)
    enabled: bool
    consent: bool


class WhatsAppSettingResponse(BaseModel):
    configured: bool
    enabled: bool
    status: str
    masked_number: str | None
    country_code: str | None
    consented_at: datetime | None
    last_tested_at: datetime | None


class WhatsAppTestResponse(BaseModel):
    notification_id: UUID
    status: str


def _source_response(source: KnowledgeSource) -> KnowledgeSourceResponse:
    return KnowledgeSourceResponse(
        id=source.id,
        type=source.source_type,
        display_name=source.safe_display_name,
        mime_type=source.mime_type,
        byte_size=source.byte_size,
        status=source.status,
        failure_code=source.failure_code,
        failure_message=source.failure_message_safe,
        indexed_at=source.indexed_at,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _require_upload_origin(request: Request, settings: Settings) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].casefold()
    if content_type != "multipart/form-data":
        raise problem(403, "csrf_rejected", "Request verification failed.")
    origin = request.headers.get("origin")
    if origin is not None and origin not in set(settings.allowed_origins):
        raise problem(403, "csrf_rejected", "Request verification failed.")
    if settings.environment in {"staging", "production"} and origin is None:
        raise problem(403, "csrf_rejected", "Request verification failed.")


async def _overview(
    session: AsyncSession,
    website_id: UUID,
    owner_user_id: UUID,
    sources: list[KnowledgeSource],
    source_limit: int,
) -> KnowledgeOverviewResponse:
    chatbot = await session.scalar(
        select(Chatbot).where(
            Chatbot.website_id == website_id, Chatbot.owner_user_id == owner_user_id
        )
    )
    active = (
        await session.get(ChatbotKnowledgeIndex, chatbot.active_index_id)
        if chatbot and chatbot.active_index_id
        else None
    )
    configured_enabled = bool((chatbot.configuration if chatbot else {}).get("enabled", True))
    state = chatbot.state if chatbot else "DISABLED"
    return KnowledgeOverviewResponse(
        chatbot_status=state,
        chatbot_enabled=configured_enabled and state != "DISABLED",
        active_index_id=active.id if active else None,
        knowledge_generation=active.knowledge_generation if active else None,
        last_indexed_at=active.activated_at if active else None,
        source_count=len(sources),
        sources=[_source_response(source) for source in sources],
        source_limit=source_limit,
    )


@router.get("/knowledge", response_model=KnowledgeOverviewResponse)
async def knowledge_overview(
    website_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeOverviewResponse:
    sources = await KnowledgeSourceService(
        session, publication_storage_for(settings), settings
    ).list_for_owner(website_id, identity.user.id)
    result = await _overview(
        session,
        website_id,
        identity.user.id,
        sources,
        settings.knowledge_max_documents_per_website,
    )
    await session.commit()
    return result


@router.post(
    "/knowledge",
    response_model=KnowledgeSourceResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_knowledge(
    website_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    file: Annotated[UploadFile, File()],
) -> KnowledgeSourceResponse:
    _require_upload_origin(request, settings)
    require_csrf(request, identity, crypto)
    recent = int(
        await session.scalar(
            select(func.count(KnowledgeSource.id)).where(
                KnowledgeSource.owner_user_id == identity.user.id,
                KnowledgeSource.created_at >= datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        or 0
    )
    if recent >= 5:
        raise problem(
            429, "knowledge_upload_rate_limited", "Please wait before uploading more documents."
        )
    data = await file.read(settings.knowledge_max_file_bytes + 1)
    source = await KnowledgeSourceService(
        session, publication_storage_for(settings), settings
    ).create(
        website_id=website_id,
        owner_user_id=identity.user.id,
        filename=file.filename or "document",
        content_type=file.content_type,
        data=data,
        correlation_id=correlation_id(request),
    )
    AuditService(session, crypto).record(
        "knowledge.uploaded",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="knowledge_source",
        target_id=str(source.id),
        reason="CHATBOT_KNOWLEDGE_UPLOAD",
        ip_address=request_ip(request, settings),
        metadata={
            "website_id": str(website_id),
            "source_type": source.source_type,
            "byte_size": source.byte_size,
        },
    )
    await session.commit()
    return _source_response(source)


@router.post("/knowledge/{source_id}/retry", response_model=KnowledgeSourceResponse)
async def retry_knowledge(
    website_id: UUID,
    source_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> KnowledgeSourceResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    source = await KnowledgeSourceService(
        session, publication_storage_for(settings), settings
    ).retry(source_id, website_id, identity.user.id, correlation_id(request))
    await session.commit()
    return _source_response(source)


@router.delete("/knowledge/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge(
    website_id: UUID,
    source_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> None:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    source = await KnowledgeSourceService(
        session, publication_storage_for(settings), settings
    ).delete(source_id, website_id, identity.user.id, correlation_id(request))
    AuditService(session, crypto).record(
        "knowledge.deleted",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="knowledge_source",
        target_id=str(source.id),
        reason="CHATBOT_KNOWLEDGE_DELETE",
        ip_address=request_ip(request, settings),
        metadata={"website_id": str(website_id)},
    )
    await session.commit()


@router.patch("/chatbot", response_model=KnowledgeOverviewResponse)
async def update_chatbot(
    website_id: UUID,
    payload: ChatbotSettingRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> KnowledgeOverviewResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    await WebsiteService(session).get_for_owner(website_id, identity.user.id)
    chatbot = await session.scalar(
        select(Chatbot)
        .where(Chatbot.website_id == website_id, Chatbot.owner_user_id == identity.user.id)
        .with_for_update()
    )
    if not chatbot:
        raise problem(
            409, "chatbot_not_provisioned", "Publish the Website before enabling its chatbot."
        )
    chatbot.configuration = {**chatbot.configuration, "enabled": payload.enabled}
    if payload.enabled:
        chatbot.state = "ACTIVE" if chatbot.active_index_id else "REQUESTED"
    else:
        chatbot.state = "DISABLED"
    chatbot.version += 1
    sources = await KnowledgeSourceService(
        session, publication_storage_for(settings), settings
    ).list_for_owner(website_id, identity.user.id)
    result = await _overview(
        session,
        website_id,
        identity.user.id,
        sources,
        settings.knowledge_max_documents_per_website,
    )
    await session.commit()
    return result


@router.post("/chatbot/preview", response_model=ChatbotPreviewResponse)
async def preview_chatbot(
    website_id: UUID,
    payload: ChatbotPreviewRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> ChatbotPreviewResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    await WebsiteService(session).get_for_owner(website_id, identity.user.id)
    service = ChatbotService.from_settings(session, publication_storage_for(settings), settings)
    conversation = await service.start_conversation(website_id, {"owner_preview": True})
    reply = await service.reply(
        website_id=website_id,
        conversation_id=conversation.conversation.id,
        access_token=conversation.access_token,
        message=payload.message,
    )
    await session.commit()
    return ChatbotPreviewResponse(answer=reply.answer, sources=reply.source_paths)


def _whatsapp_response(
    setting: WhatsAppNotificationSetting | None,
) -> WhatsAppSettingResponse:
    return WhatsAppSettingResponse(
        configured=setting is not None,
        enabled=bool(setting and setting.enabled),
        status=setting.status if setting else "DISABLED",
        masked_number=f"Ending in {setting.phone_last4}" if setting else None,
        country_code=setting.country_code if setting else None,
        consented_at=setting.consented_at if setting else None,
        last_tested_at=setting.last_tested_at if setting else None,
    )


@router.get("/whatsapp-notifications", response_model=WhatsAppSettingResponse)
async def whatsapp_setting(
    website_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> WhatsAppSettingResponse:
    await WebsiteService(session).get_for_owner(website_id, identity.user.id)
    setting = await WhatsAppNotificationService(session, crypto, settings).setting_for(
        identity.user.id
    )
    await session.commit()
    return _whatsapp_response(setting)


@router.patch("/whatsapp-notifications", response_model=WhatsAppSettingResponse)
async def update_whatsapp_setting(
    website_id: UUID,
    payload: WhatsAppSettingRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> WhatsAppSettingResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    await WebsiteService(session).get_for_owner(website_id, identity.user.id)
    setting = await WhatsAppNotificationService(session, crypto, settings).update_setting(
        owner_user_id=identity.user.id,
        phone_number=payload.phone_number,
        country_code=payload.country_code,
        enabled=payload.enabled,
        consent=payload.consent,
    )
    AuditService(session, crypto).record(
        "whatsapp.setting_updated",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="whatsapp_notification_setting",
        target_id=str(setting.id),
        reason="OWNER_NOTIFICATION_SETTING",
        ip_address=request_ip(request, settings),
        metadata={"enabled": setting.enabled, "country_code": setting.country_code},
    )
    await session.commit()
    return _whatsapp_response(setting)


@router.post("/whatsapp-notifications/test", response_model=WhatsAppTestResponse, status_code=202)
async def test_whatsapp(
    website_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> WhatsAppTestResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    await WebsiteService(session).get_for_owner(website_id, identity.user.id)
    recent = int(
        await session.scalar(
            select(func.count(WhatsAppNotification.id)).where(
                WhatsAppNotification.owner_user_id == identity.user.id,
                WhatsAppNotification.kind == "TEST",
                WhatsAppNotification.created_at >= datetime.now(UTC) - timedelta(minutes=5),
            )
        )
        or 0
    )
    if recent >= 1:
        raise problem(
            429, "whatsapp_test_rate_limited", "Wait five minutes before sending another test."
        )
    notification = await WhatsAppNotificationService(session, crypto, settings).queue_test(
        owner_user_id=identity.user.id,
        country_code=identity.user.billing_country_code,
        correlation_id=correlation_id(request),
    )
    await session.commit()
    return WhatsAppTestResponse(notification_id=notification.id, status=notification.state)
