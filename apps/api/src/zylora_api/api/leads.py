from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.db.lead_models import Lead
from zylora_api.db.session import get_session
from zylora_api.modules.auth.http import RequestIdentity, get_user_identity
from zylora_api.modules.leads.credits import CreditLedgerService, LeadCreditPolicyService
from zylora_api.modules.leads.schemas import LeadCreditResponse, LeadOwnerResponse

router = APIRouter(prefix="/api/v1", tags=["leads"])


@router.get("/websites/{website_id}/leads", response_model=list[LeadOwnerResponse])
async def website_leads(
    website_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[LeadOwnerResponse]:
    leads = list(
        (
            await session.scalars(
                select(Lead)
                .where(Lead.website_id == website_id, Lead.owner_user_id == identity.user.id)
                .order_by(Lead.captured_at.desc())
                .limit(limit)
            )
        ).all()
    )
    await session.commit()
    return [
        LeadOwnerResponse(
            id=item.id,
            source=item.source,
            name=item.name,
            email=item.email,
            phone=item.phone,
            enquiry=item.enquiry,
            page_path=item.page_path,
            status=item.status,
            captured_at=item.captured_at.isoformat(),
        )
        for item in leads
    ]


@router.get("/lead-credits", response_model=LeadCreditResponse)
async def lead_credits(
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LeadCreditResponse:
    balance = await CreditLedgerService(session).balance_for(identity.user.id)
    policy = await LeadCreditPolicyService(session).current()
    await session.commit()
    return LeadCreditResponse(balance=balance, policy=policy.policy)
