from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.lead_models import ProLead
from zylora_api.db.session import get_session
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.challenge import ChallengeService, CloudflareTurnstileVerifier
from zylora_api.modules.auth.http import (
    RequestIdentity,
    correlation_id,
    get_admin_identity,
    get_crypto,
    get_turnstile_verifier,
    request_ip,
    require_csrf,
    require_json_origin,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.pro_leads.schemas import (
    ProLeadCreateRequest,
    ProLeadListResponse,
    ProLeadResponse,
    ProLeadStatusUpdateRequest,
    ProLeadSummaryResponse,
)
from zylora_api.modules.pro_leads.service import ProLeadService

router = APIRouter(prefix="/api/v1", tags=["pro-leads"])


def _to_response(pro_lead: ProLead) -> ProLeadResponse:
    return ProLeadResponse(
        id=pro_lead.id,
        reference_id=pro_lead.reference_id,
        name=pro_lead.name,
        email=pro_lead.email,
        website_type=pro_lead.website_type,
        preferred_contact_time=pro_lead.preferred_contact_time,
        status=pro_lead.status,
        amount_received=pro_lead.amount_received,
        submitted_at=pro_lead.submitted_at,
        resolved_at=pro_lead.resolved_at,
    )


@router.post(
    "/public/pro-enquiry",
    response_model=ProLeadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_pro_enquiry(
    payload: ProLeadCreateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    verifier: Annotated[CloudflareTurnstileVerifier, Depends(get_turnstile_verifier)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> ProLeadResponse:
    require_json_origin(request, settings)
    challenge_service = ChallengeService(session, settings, crypto, verifier)
    service = ProLeadService(
        session,
        settings,
        challenge_service=challenge_service,
        crypto=crypto,
    )
    ip = request_ip(request, settings)
    cid = correlation_id(request)
    pro_lead = await service.submit_pro_enquiry(payload, client_ip=ip, correlation_id=cid)
    await session.commit()
    return _to_response(pro_lead)


@router.get(
    "/admin/pro-leads",
    response_model=ProLeadListResponse,
)
async def list_admin_pro_leads(
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProLeadListResponse:
    service = ProLeadService(session, settings)
    leads = await service.list_pro_leads()
    summary = await service.get_summary()
    return ProLeadListResponse(
        items=[_to_response(item) for item in leads],
        summary=summary,
    )


@router.get(
    "/admin/pro-leads/summary",
    response_model=ProLeadSummaryResponse,
)
async def get_admin_pro_lead_summary(
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProLeadSummaryResponse:
    service = ProLeadService(session, settings)
    return await service.get_summary()


@router.patch(
    "/admin/pro-leads/{pro_lead_id}/status",
    response_model=ProLeadResponse,
)
async def update_pro_lead_status(
    pro_lead_id: UUID,
    payload: ProLeadStatusUpdateRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> ProLeadResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    service = ProLeadService(session, settings)
    pro_lead = await service.update_status(
        pro_lead_id, payload.status, amount_received=payload.amount_received
    )
    AuditService(session, crypto).record(
        "pro_lead.status_updated",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="pro_lead",
        target_id=str(pro_lead_id),
        reason=f"ADMIN_MARK_{payload.status}",
        ip_address=request_ip(request, settings),
        metadata={
            "status": payload.status,
            "amount_received": payload.amount_received,
        },
    )
    await session.commit()
    return _to_response(pro_lead)
