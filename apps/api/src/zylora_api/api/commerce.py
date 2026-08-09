from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_session
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
from zylora_api.modules.commerce.ownership import OwnershipService
from zylora_api.modules.commerce.ownership_schemas import (
    OwnershipTransferRequest,
    OwnershipTransferResponse,
)
from zylora_api.modules.commerce.publishing import PublishEligibilityService, PublishService
from zylora_api.modules.commerce.schemas import (
    CancelSubscriptionResponse,
    CheckoutRequest,
    CheckoutResponse,
    MoneyResponse,
    PlanListResponse,
    PublishCommandResponse,
    PublishEvaluationResponse,
    PublishRequest,
    SubscriptionResponse,
    UnpublishCommandResponse,
)
from zylora_api.modules.commerce.service import CatalogService, SubscriptionService
from zylora_api.modules.templates.service import problem

router = APIRouter(prefix="/api/v1", tags=["commerce"])
COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")


def request_country(request: Request, settings: Settings, user: User | None = None) -> str:
    if user and user.billing_country_code != "ZZ":
        return user.billing_country_code
    country = "ZZ"
    if settings.cloudflare_country_header_trusted:
        candidate = request.headers.get("cf-ipcountry", "").upper()
        if COUNTRY_PATTERN.fullmatch(candidate) and candidate not in {"XX", "T1"}:
            country = candidate
    if user and country != "ZZ":
        user.billing_country_code = country
    return country


def require_idempotency_key(value: str | None) -> str:
    if not value or not (16 <= len(value) <= 160):
        raise problem(
            422,
            "idempotency_key_required",
            "Provide an Idempotency-Key between 16 and 160 characters.",
        )
    return value


@router.get("/plans", response_model=PlanListResponse)
async def plans(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlanListResponse:
    result = await CatalogService(session).response(request_country(request, settings))
    await session.commit()
    return result


@router.get("/billing/subscription", response_model=SubscriptionResponse)
async def subscription(
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SubscriptionResponse:
    country = request_country(request, settings, identity.user)
    result = await SubscriptionService(session).response(identity.user.id, country)
    await session.commit()
    return result


@router.post("/billing/subscription/checkouts", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CheckoutResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    country = request_country(request, settings, identity.user)
    payment = await SubscriptionService(session).create_payment(
        identity.user.id,
        country,
        payload.plan_id,
        require_idempotency_key(idempotency_key),
    )
    AuditService(session, crypto).record(
        "billing.checkout_requested",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="payment",
        target_id=str(payment.id),
        reason="SUBSCRIPTION_CHECKOUT",
        ip_address=request_ip(request, settings),
        metadata={
            "plan_id": str(payment.plan_id),
            "amount_minor": payment.expected_amount_minor,
            "currency": payment.expected_currency,
        },
    )
    await session.commit()
    return CheckoutResponse(
        payment_id=payment.id,
        status=payment.state,
        price=MoneyResponse(
            amount_minor=payment.expected_amount_minor,
            currency=payment.expected_currency,
        ),
        provider_available=False,
        detail=(
            "Your server-authoritative price snapshot is saved. Paid checkout remains unavailable "
            "until an approved production payment provider is configured."
        ),
    )


@router.post("/billing/subscription/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> CancelSubscriptionResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    result = await SubscriptionService(session).cancel(
        identity.user.id, request_country(request, settings, identity.user)
    )
    AuditService(session, crypto).record(
        "billing.subscription_cancelled",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="subscription",
        target_id=str(identity.user.id),
        reason="CANCEL_AT_PERIOD_END",
        ip_address=request_ip(request, settings),
        metadata={
            "plan_code": result.plan_code,
            "period_end": result.current_period_end.isoformat(),
        },
    )
    await session.commit()
    return result


@router.get("/websites/{website_id}/publish-evaluation", response_model=PublishEvaluationResponse)
async def publish_evaluation(
    website_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    domain_type: Annotated[str, Query(pattern="^(ZYLORA_SUBDOMAIN|CUSTOM)$")] = "ZYLORA_SUBDOMAIN",
) -> PublishEvaluationResponse:
    result = await PublishEligibilityService(session).evaluate(
        website_id,
        identity.user.id,
        request_country(request, settings, identity.user),
        domain_type,
    )
    await session.commit()
    return result


@router.post(
    "/websites/{website_id}/publish", response_model=PublishCommandResponse, status_code=202
)
async def publish(
    website_id: UUID,
    payload: PublishRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PublishCommandResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    result = await PublishService(session).request_publish(
        website_id,
        identity.user.id,
        request_country(request, settings, identity.user),
        payload.domain_type,
        require_idempotency_key(idempotency_key),
        correlation_id(request),
    )
    AuditService(session, crypto).record(
        "website.publish_requested",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website",
        target_id=str(website_id),
        reason="PUBLISH_ELIGIBLE",
        ip_address=request_ip(request, settings),
        metadata={"plan_code": result.plan_code, "domain_type": payload.domain_type},
    )
    await session.commit()
    return result


@router.post(
    "/websites/{website_id}/unpublish", response_model=UnpublishCommandResponse, status_code=202
)
async def unpublish(
    website_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> UnpublishCommandResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    result = await PublishService(session).request_unpublish(
        website_id, identity.user.id, correlation_id(request)
    )
    await session.commit()
    return result


@router.post("/websites/{website_id}/transfers", response_model=OwnershipTransferResponse)
async def transfer(
    website_id: UUID,
    payload: OwnershipTransferRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OwnershipTransferResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    recipient, _ = crypto.normalize_email(str(payload.recipient_email))
    result = await OwnershipService(session).transfer(
        website_id,
        identity.user.id,
        recipient,
        require_idempotency_key(idempotency_key),
    )
    AuditService(session, crypto).record(
        "website.ownership_transferred",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website",
        target_id=str(website_id),
        reason="OWNER_TRANSFER",
        ip_address=request_ip(request, settings),
        metadata={"recipient_user_id": str(result.recipient_user_id)},
    )
    await session.commit()
    return OwnershipTransferResponse(
        id=result.id,
        website_id=result.website_id,
        sender_user_id=result.sender_user_id,
        recipient_user_id=result.recipient_user_id,
        status=result.status,
        completed_at=result.completed_at,
    )
