from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_session
from zylora_api.modules.analytics.activation import ProductAnalyticsService
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
from zylora_api.modules.commerce.export_schemas import (
    ExportCheckoutResponse,
    ExportGenerationResponse,
    ExportPurchaseResponse,
)
from zylora_api.modules.commerce.exports import ExportService, purchase_response
from zylora_api.modules.commerce.ownership import OwnershipService
from zylora_api.modules.commerce.ownership_schemas import (
    OwnershipTransferRequest,
    OwnershipTransferResponse,
    OwnershipTransferValidationRequest,
    OwnershipTransferValidationResponse,
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
from zylora_api.modules.publishing.runtime import publication_storage_for
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
    await ProductAnalyticsService(session).record_event(
        event_type="PLAN_UPGRADE_STARTED",
        idempotency_key=f"plan-upgrade-started:{payment.id}",
        user_id=identity.user.id,
        properties={"plan_id": str(payment.plan_id)},
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
    await ProductAnalyticsService(session).record_event(
        event_type="SUBSCRIPTION_CANCELLED",
        idempotency_key=f"subscription-cancelled:{identity.user.id}:{result.current_period_end.isoformat()}",
        user_id=identity.user.id,
        properties={"plan_code": result.plan_code},
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
    publish_service = PublishService(session)
    publish_kwargs = {"hostname": payload.hostname} if payload.hostname is not None else {}
    publish_key = require_idempotency_key(idempotency_key)
    result = await publish_service.request_publish(
        website_id,
        identity.user.id,
        request_country(request, settings, identity.user),
        payload.domain_type,
        publish_key,
        correlation_id(request),
        **publish_kwargs,
    )
    await ProductAnalyticsService(session).record_event(
        event_type="SITE_PUBLISH_REQUESTED",
        idempotency_key=f"site-publish-requested:{website_id}:{publish_key}",
        user_id=identity.user.id,
        website_id=website_id,
        properties={"domain_type": payload.domain_type},
    )
    AuditService(session, crypto).record(
        "website.publish_requested",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website",
        target_id=str(website_id),
        reason="PUBLISH_ELIGIBLE",
        ip_address=request_ip(request, settings),
        metadata={
            "plan_code": result.plan_code,
            "domain_type": payload.domain_type,
            "deployment_id": str(result.deployment_id) if result.deployment_id else None,
        },
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


def transfer_response(result: object) -> OwnershipTransferResponse:
    return OwnershipTransferResponse(
        id=result.id,  # type: ignore[attr-defined]
        website_id=result.website_id,  # type: ignore[attr-defined]
        sender_user_id=result.sender_user_id,  # type: ignore[attr-defined]
        recipient_user_id=result.recipient_user_id,  # type: ignore[attr-defined]
        status=result.status,  # type: ignore[attr-defined]
        failure_code=result.failure_code,  # type: ignore[attr-defined]
        validated_at=result.validated_at,  # type: ignore[attr-defined]
        completed_at=result.completed_at,  # type: ignore[attr-defined]
    )


@router.post(
    "/websites/{website_id}/transfers/validate",
    response_model=OwnershipTransferValidationResponse,
)
async def validate_transfer(
    website_id: UUID,
    payload: OwnershipTransferValidationRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> OwnershipTransferValidationResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    recipient_email, _ = crypto.normalize_email(str(payload.recipient_email))
    website, recipient = await OwnershipService(session).validate_recipient(
        website_id, identity.user.id, recipient_email
    )
    AuditService(session, crypto).record(
        "website.ownership_transfer_validated",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website",
        target_id=str(website.id),
        reason="OWNER_TRANSFER_RECIPIENT_VALIDATED",
        ip_address=request_ip(request, settings),
        metadata={"recipient_user_id": str(recipient.id)},
    )
    await session.commit()
    return OwnershipTransferValidationResponse(
        website_id=website.id,
        recipient_email=recipient.display_email,
        eligible=True,
        requires_route_deactivation=website.status == "PUBLISHED",
    )


@router.post(
    "/websites/{website_id}/transfers", response_model=OwnershipTransferResponse, status_code=202
)
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
    result = await OwnershipService(session).start_transfer(
        website_id,
        identity.user.id,
        recipient,
        payload.confirmation_version,
        require_idempotency_key(idempotency_key),
        correlation_id(request),
    )
    AuditService(session, crypto).record(
        "website.ownership_transfer_requested",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website",
        target_id=str(website_id),
        reason="OWNER_TRANSFER",
        ip_address=request_ip(request, settings),
        metadata={
            "recipient_user_id": str(result.recipient_user_id),
            "transfer_id": str(result.id),
            "status": result.status,
        },
    )
    await session.commit()
    return transfer_response(result)


@router.get(
    "/websites/{website_id}/transfers/{transfer_id}", response_model=OwnershipTransferResponse
)
async def transfer_status(
    website_id: UUID,
    transfer_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OwnershipTransferResponse:
    result = await OwnershipService(session).get_for_owner(transfer_id, identity.user.id)
    if result.website_id != website_id:
        raise problem(404, "ownership_transfer_not_found", "Ownership transfer not found.")
    await session.commit()
    return transfer_response(result)


@router.post(
    "/websites/{website_id}/exports", response_model=ExportPurchaseResponse, status_code=201
)
async def create_export_purchase(
    website_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ExportPurchaseResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    purchase = await ExportService(session).create_purchase(
        website_id,
        identity.user.id,
        request_country(request, settings, identity.user),
        require_idempotency_key(idempotency_key),
    )
    AuditService(session, crypto).record(
        "website.export_purchase_created",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website_export",
        target_id=str(purchase.id),
        reason="EXPORT_PRICE_SNAPSHOTTED",
        ip_address=request_ip(request, settings),
        metadata={
            "website_id": str(website_id),
            "amount_minor": purchase.amount_minor,
            "currency": purchase.currency,
            "price_version": purchase.price_version,
        },
    )
    await session.commit()
    return purchase_response(purchase)


@router.get("/website-exports/{purchase_id}", response_model=ExportPurchaseResponse)
async def export_status(
    purchase_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExportPurchaseResponse:
    purchase = await ExportService(session).get_for_owner(purchase_id, identity.user.id)
    await session.commit()
    return purchase_response(purchase)


@router.post("/website-exports/{purchase_id}/checkout", response_model=ExportCheckoutResponse)
async def export_checkout(
    purchase_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> ExportCheckoutResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    purchase, payment = await ExportService(session).checkout(purchase_id, identity.user.id)
    AuditService(session, crypto).record(
        "website.export_checkout_requested",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="payment",
        target_id=str(payment.id),
        reason="EXPORT_CHECKOUT",
        ip_address=request_ip(request, settings),
        metadata={"purchase_id": str(purchase.id), "amount_minor": purchase.amount_minor},
    )
    await session.commit()
    return ExportCheckoutResponse(
        purchase=purchase_response(purchase),
        payment_id=payment.id,
        provider_available=False,
        detail=(
            "Your server-authoritative export price is saved. Paid checkout remains unavailable "
            "until an approved production payment provider is configured."
        ),
    )


@router.post(
    "/website-exports/{purchase_id}/generate",
    response_model=ExportGenerationResponse,
    status_code=202,
)
async def generate_export(
    purchase_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> ExportGenerationResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    purchase, queued = await ExportService(session).queue_generation(
        purchase_id, identity.user.id, correlation_id(request)
    )
    AuditService(session, crypto).record(
        "website.export_generation_requested",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website_export",
        target_id=str(purchase.id),
        reason="VERIFIED_EXPORT_PAYMENT",
        ip_address=request_ip(request, settings),
        metadata={"queued": queued},
    )
    await session.commit()
    return ExportGenerationResponse(purchase=purchase_response(purchase), queued=queued)


@router.get("/website-exports/{purchase_id}/download")
async def download_export(
    purchase_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> Response:
    service = ExportService(session)
    artifact = await service.artifact_for_download(purchase_id, identity.user.id)
    AuditService(session, crypto).record(
        "website.export_download_authorized",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website_export",
        target_id=str(purchase_id),
        reason="READY_PRIVATE_ARTIFACT",
        ip_address=request_ip(request, settings),
    )
    storage = publication_storage_for(settings)
    await session.commit()
    if settings.environment == "test":
        data = await run_in_threadpool(storage.get_bytes, artifact.object_key)
        return Response(
            content=data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="zylora-website-{purchase_id}.zip"',
                "Cache-Control": "private, no-store",
            },
        )
    try:
        signed_url = await run_in_threadpool(storage.presign_get, artifact.object_key, 300)
    except RuntimeError as error:
        raise problem(
            503,
            "website_export_storage_unavailable",
            "Website export delivery is temporarily unavailable.",
        ) from error
    return RedirectResponse(signed_url, status_code=307, headers={"Cache-Control": "no-store"})
