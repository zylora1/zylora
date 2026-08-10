from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
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
from zylora_api.modules.commerce.export_schemas import (
    ExportPriceConfigureRequest,
    ExportPriceResponse,
)
from zylora_api.modules.commerce.exports import ExportPriceService, price_response

router = APIRouter(prefix="/api/v1", tags=["admin-exports"])


@router.get("/admin/export-prices", response_model=list[ExportPriceResponse])
async def export_prices(
    _: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ExportPriceResponse]:
    prices = await ExportPriceService(session).list_prices()
    await session.commit()
    return [price_response(price) for price in prices]


@router.post(
    "/admin/export-prices", response_model=ExportPriceResponse, status_code=status.HTTP_201_CREATED
)
async def configure_export_price(
    payload: ExportPriceConfigureRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> ExportPriceResponse:
    require_json_origin(request, settings, admin=True)
    require_csrf(request, identity, crypto)
    price = await ExportPriceService(session).configure(
        currency=payload.currency,
        amount_minor=payload.amount_minor,
        active=payload.active,
        configured_by_user_id=identity.user.id,
    )
    AuditService(session, crypto).record(
        "commerce.export_price_configured",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="export_price",
        target_id=str(price.id),
        reason="SUPER_ADMIN_EXPORT_PRICE_CONFIGURATION",
        ip_address=request_ip(request, settings),
        metadata={
            "currency": price.currency,
            "amount_minor": price.amount_minor,
            "version": price.version,
            "active": price.active,
        },
    )
    await session.commit()
    return price_response(price)
