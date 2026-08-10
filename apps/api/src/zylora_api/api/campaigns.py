from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_session
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.http import (
    RequestIdentity,
    correlation_id,
    get_admin_identity,
    get_crypto,
    request_ip,
    require_csrf,
    require_json_origin,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.campaigns.schemas import (
    AdministrativeEmailRequest,
    CampaignReasonRequest,
    CampaignRequest,
    CampaignResponse,
    CampaignScheduleRequest,
    UnsubscribeRequest,
)
from zylora_api.modules.campaigns.service import CampaignService, CampaignSummary
from zylora_api.modules.notifications.email import TransactionalEmailService
from zylora_api.modules.templates.service import problem

router = APIRouter(prefix="/api/v1", tags=["super-admin-campaigns"])


def _command(
    request: Request, identity: RequestIdentity, settings: Settings, crypto: AuthCrypto
) -> None:
    require_json_origin(request, settings, admin=True)
    require_csrf(request, identity, crypto)


def _response(row: CampaignSummary) -> CampaignResponse:
    return CampaignResponse(**row.__dict__)


@router.get("/admin/campaigns", response_model=list[CampaignResponse])
async def campaigns(
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> list[CampaignResponse]:
    rows = await CampaignService(session, crypto).list()
    return [_response(row) for row in rows]


@router.post(
    "/admin/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED
)
async def create_campaign(
    payload: CampaignRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> CampaignResponse:
    _command(request, identity, settings, crypto)
    service = CampaignService(session, crypto)
    campaign = await service.create(actor_user_id=identity.user.id, **payload.model_dump())
    AuditService(session, crypto).record(
        "campaign.created",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="campaign",
        target_id=str(campaign.id),
        reason="SUPER_ADMIN_CAMPAIGN_CREATE",
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    return _response((await service.list(1))[0])


@router.patch("/admin/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> CampaignResponse:
    _command(request, identity, settings, crypto)
    service = CampaignService(session, crypto)
    campaign = await service.update(campaign_id, **payload.model_dump())
    AuditService(session, crypto).record(
        "campaign.updated",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="campaign",
        target_id=str(campaign.id),
        reason="SUPER_ADMIN_CAMPAIGN_UPDATE",
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        subject=campaign.subject,
        state=campaign.state,
        audience_type=campaign.audience_type,
        audience_plan_code=campaign.audience_plan_code,
        audience_snapshot_count=campaign.audience_snapshot_count,
        scheduled_at=campaign.scheduled_at,
        created_at=campaign.created_at,
    )


async def _transition(
    action: str,
    campaign_id: UUID,
    payload: CampaignReasonRequest,
    request: Request,
    identity: RequestIdentity,
    session: AsyncSession,
    settings: Settings,
    crypto: AuthCrypto,
) -> CampaignResponse:
    _command(request, identity, settings, crypto)
    service = CampaignService(session, crypto)
    campaign = await getattr(service, action)(campaign_id)
    AuditService(session, crypto).record(
        f"campaign.{action}",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="campaign",
        target_id=str(campaign.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
        metadata={"outcome": campaign.state},
    )
    await session.commit()
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        subject=campaign.subject,
        state=campaign.state,
        audience_type=campaign.audience_type,
        audience_plan_code=campaign.audience_plan_code,
        audience_snapshot_count=campaign.audience_snapshot_count,
        scheduled_at=campaign.scheduled_at,
        created_at=campaign.created_at,
    )


@router.post("/admin/campaigns/{campaign_id}/ready", response_model=CampaignResponse)
async def prepare_campaign(
    campaign_id: UUID,
    payload: CampaignReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> CampaignResponse:
    return await _transition(
        "ready", campaign_id, payload, request, identity, session, settings, crypto
    )


@router.post("/admin/campaigns/{campaign_id}/cancel", response_model=CampaignResponse)
async def cancel_campaign(
    campaign_id: UUID,
    payload: CampaignReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> CampaignResponse:
    return await _transition(
        "cancel", campaign_id, payload, request, identity, session, settings, crypto
    )


@router.post("/admin/campaigns/{campaign_id}/send", response_model=CampaignResponse)
async def send_campaign(
    campaign_id: UUID,
    payload: CampaignReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> CampaignResponse:
    _command(request, identity, settings, crypto)
    service = CampaignService(session, crypto)
    campaign = await service.start(campaign_id, correlation_id=correlation_id(request))
    AuditService(session, crypto).record(
        "campaign.send_started",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="campaign",
        target_id=str(campaign.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
        metadata={"audience_snapshot_count": campaign.audience_snapshot_count},
    )
    await session.commit()
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        subject=campaign.subject,
        state=campaign.state,
        audience_type=campaign.audience_type,
        audience_plan_code=campaign.audience_plan_code,
        audience_snapshot_count=campaign.audience_snapshot_count,
        scheduled_at=campaign.scheduled_at,
        created_at=campaign.created_at,
    )


@router.post("/admin/campaigns/{campaign_id}/schedule", response_model=CampaignResponse)
async def schedule_campaign(
    campaign_id: UUID,
    payload: CampaignScheduleRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> CampaignResponse:
    _command(request, identity, settings, crypto)
    service = CampaignService(session, crypto)
    campaign = await service.schedule(campaign_id, payload.scheduled_at)
    AuditService(session, crypto).record(
        "campaign.scheduled",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="campaign",
        target_id=str(campaign.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
        metadata={
            "scheduled_at": campaign.scheduled_at.isoformat() if campaign.scheduled_at else None
        },
    )
    await session.commit()
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        subject=campaign.subject,
        state=campaign.state,
        audience_type=campaign.audience_type,
        audience_plan_code=campaign.audience_plan_code,
        audience_snapshot_count=campaign.audience_snapshot_count,
        scheduled_at=campaign.scheduled_at,
        created_at=campaign.created_at,
    )


@router.post("/admin/users/{user_id}/administrative-email", status_code=status.HTTP_202_ACCEPTED)
async def send_administrative_email(
    user_id: UUID,
    payload: AdministrativeEmailRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> dict[str, str]:
    _command(request, identity, settings, crypto)
    user = await session.scalar(select(User).where(User.id == user_id, User.account_type == "USER"))
    if not user:
        raise problem(404, "user_not_found", "User not found.")
    content_digest = crypto.digest(payload.subject + payload.body, purpose="admin-email").hex()
    email = await TransactionalEmailService(session, crypto).queue(
        recipient_email=user.display_email,
        recipient_user_id=user.id,
        kind="ADMIN_TRANSACTIONAL",
        resource_type="user",
        resource_id=user.id,
        idempotency_key=f"admin-email:{identity.user.id}:{user.id}:{content_digest}",
        subject=payload.subject,
        body=payload.body,
        correlation_id=correlation_id(request),
    )
    AuditService(session, crypto).record(
        "admin.transactional_email_queued",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="transactional_email",
        target_id=str(email.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
        metadata={"recipient_user_id": str(user.id), "kind": email.kind},
    )
    await session.commit()
    return {"status": "queued", "id": str(email.id)}


@router.post("/public/marketing/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    payload: UnsubscribeRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> None:
    await CampaignService(session, crypto).unsubscribe(payload.token)
    await session.commit()
