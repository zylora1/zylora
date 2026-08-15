from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
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
from zylora_api.modules.leads.credits import CreditLedgerService, LeadCreditPolicyService
from zylora_api.modules.leads.schemas import (
    LeadCreditAdjustmentRequest,
    LeadCreditAdjustmentResponse,
    LeadCreditPolicyRequest,
    LeadCreditResponse,
)
from zylora_api.modules.templates.service import problem

router = APIRouter(prefix="/api/v1", tags=["admin-leads"])


def require_idempotency_key(value: str | None) -> str:
    if not value or not 16 <= len(value) <= 160:
        raise problem(422, "idempotency_key_required", "Provide a valid Idempotency-Key.")
    return value


@router.get("/admin/lead-credit-policy", response_model=LeadCreditResponse)
async def lead_credit_policy(
    _: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LeadCreditResponse:
    policy = await LeadCreditPolicyService(session).current()
    await session.commit()
    return LeadCreditResponse(balance=0, policy=policy.policy)


@router.post("/admin/lead-credit-policy", response_model=LeadCreditResponse)
async def configure_lead_credit_policy(
    payload: LeadCreditPolicyRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> LeadCreditResponse:
    require_json_origin(request, settings, admin=True)
    require_csrf(request, identity, crypto)
    policy = await LeadCreditPolicyService(session).configure(payload.policy)
    AuditService(session, crypto).record(
        "leads.zero_credit_policy_configured",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="platform_setting",
        target_id="lead_zero_balance_policy",
        reason="SUPER_ADMIN_LEAD_CREDIT_POLICY",
        ip_address=request_ip(request, settings),
        metadata={"policy": policy.policy},
    )
    await session.commit()
    return LeadCreditResponse(balance=0, policy=policy.policy)


@router.post("/admin/users/{user_id}/lead-credits", response_model=LeadCreditAdjustmentResponse)
async def adjust_lead_credits(
    user_id: UUID,
    payload: LeadCreditAdjustmentRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> LeadCreditAdjustmentResponse:
    require_json_origin(request, settings, admin=True)
    require_csrf(request, identity, crypto)
    ledger = await CreditLedgerService(session).adjust(
        user_id=user_id,
        actor_user_id=identity.user.id,
        delta=payload.delta,
        idempotency_key=require_idempotency_key(idempotency_key),
        reason=payload.reason,
    )
    AuditService(session, crypto).record(
        "leads.credit_adjusted",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="lead_credit_ledger",
        target_id=str(ledger.id),
        reason="SUPER_ADMIN_LEAD_CREDIT_ADJUSTMENT",
        ip_address=request_ip(request, settings),
        metadata={"user_id": str(user_id), "delta": ledger.delta, "reason": ledger.reason},
    )
    await session.commit()
    return LeadCreditAdjustmentResponse(
        user_id=user_id,
        delta=ledger.delta,
        resulting_balance=ledger.resulting_balance,
        entry_type=ledger.entry_type,
    )
