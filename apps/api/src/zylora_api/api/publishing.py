from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.deployment_models import Deployment, Domain
from zylora_api.db.session import get_session
from zylora_api.db.website_models import Website
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
from zylora_api.modules.publishing.providers import domain_provider_for
from zylora_api.modules.publishing.schemas import (
    DeploymentResponse,
    DomainCreateRequest,
    DomainResponse,
    PublicationStatusResponse,
    RollbackRequest,
)
from zylora_api.modules.publishing.service import DeploymentService, DomainService
from zylora_api.modules.templates.service import problem

router = APIRouter(prefix="/api/v1", tags=["publishing"])


def _idempotency_key(value: str | None) -> str:
    if not value or not 16 <= len(value) <= 160:
        raise problem(422, "idempotency_key_required", "Provide a valid Idempotency-Key.")
    return value


async def _website_for_owner(
    session: AsyncSession, website_id: UUID, owner_user_id: UUID
) -> Website:
    website = await session.scalar(
        select(Website).where(Website.id == website_id, Website.owner_user_id == owner_user_id)
    )
    if not website:
        raise problem(404, "website_not_found", "Website not found.")
    return website


def _domain_response(domain: Domain) -> DomainResponse:
    return DomainResponse(
        id=domain.id,
        website_id=domain.website_id,
        type=domain.type,
        hostname=domain.display_hostname,
        state=domain.state,
        tls_status=domain.tls_status,
        is_primary=domain.is_primary,
        is_active=domain.is_active,
        verification_record_name=domain.verification_record_name,
        verification_record_type=domain.verification_record_type,
        verification_record_value=domain.verification_record_value,
        safe_error=domain.safe_error,
        updated_at=domain.updated_at,
    )


def _deployment_response(deployment: Deployment) -> DeploymentResponse:
    return DeploymentResponse(
        id=deployment.id,
        website_id=deployment.website_id,
        domain_id=deployment.domain_id,
        operation=deployment.operation,
        state=deployment.state,
        artifact_checksum=deployment.artifact_checksum,
        failure_code=deployment.failure_code,
        safe_error=deployment.safe_error,
        queued_at=deployment.queued_at,
        completed_at=deployment.completed_at,
    )


@router.get("/websites/{website_id}/publication", response_model=PublicationStatusResponse)
async def publication_status(
    website_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PublicationStatusResponse:
    website = await _website_for_owner(session, website_id, identity.user.id)
    domains = list(
        (
            await session.scalars(
                select(Domain)
                .where(Domain.website_id == website.id)
                .order_by(Domain.created_at.desc())
            )
        ).all()
    )
    deployments = list(
        (
            await session.scalars(
                select(Deployment)
                .where(Deployment.website_id == website.id)
                .order_by(Deployment.queued_at.desc())
                .limit(50)
            )
        ).all()
    )
    return PublicationStatusResponse(
        website_id=website.id,
        website_status=website.status,
        active_deployment_id=website.active_deployment_id,
        domains=[_domain_response(domain) for domain in domains],
        deployments=[_deployment_response(deployment) for deployment in deployments],
    )


@router.get("/websites/{website_id}/domains", response_model=list[DomainResponse])
async def domains(
    website_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DomainResponse]:
    await _website_for_owner(session, website_id, identity.user.id)
    result = await DomainService(session).list_for_owner(website_id, identity.user.id)
    return [_domain_response(domain) for domain in result]


@router.post(
    "/websites/{website_id}/domains/custom", response_model=DomainResponse, status_code=201
)
async def create_custom_domain(
    website_id: UUID,
    payload: DomainCreateRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DomainResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    domain = await DomainService(session).create_custom(
        website_id,
        identity.user.id,
        payload.hostname,
        _idempotency_key(idempotency_key),
        domain_provider_for(settings),
    )
    AuditService(session, crypto).record(
        "website.custom_domain_requested",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="domain",
        target_id=str(domain.id),
        reason="CUSTOM_DOMAIN_REQUESTED",
        ip_address=request_ip(request, settings),
        metadata={"website_id": str(website_id), "domain_type": domain.type},
    )
    await session.commit()
    await session.refresh(domain)
    return _domain_response(domain)


@router.post("/websites/{website_id}/domains/{domain_id}/verify", response_model=DomainResponse)
async def verify_custom_domain(
    website_id: UUID,
    domain_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> DomainResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    await _website_for_owner(session, website_id, identity.user.id)
    requested_domain = await session.scalar(
        select(Domain).where(
            Domain.id == domain_id,
            Domain.website_id == website_id,
            Domain.owner_user_id == identity.user.id,
            Domain.type == "CUSTOM",
        )
    )
    if not requested_domain:
        raise problem(404, "domain_not_found", "Custom domain not found.")
    domain = await DomainService(session).verify_custom(
        domain_id, identity.user.id, domain_provider_for(settings)
    )
    AuditService(session, crypto).record(
        "website.custom_domain_verification_checked",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="domain",
        target_id=str(domain.id),
        reason="CUSTOM_DOMAIN_VERIFY",
        ip_address=request_ip(request, settings),
        metadata={"website_id": str(website_id), "state": domain.state},
    )
    await session.commit()
    return _domain_response(domain)


@router.post("/websites/{website_id}/rollbacks", response_model=DeploymentResponse, status_code=202)
async def rollback(
    website_id: UUID,
    payload: RollbackRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DeploymentResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    deployment = await DeploymentService(session).queue_rollback(
        website_id,
        identity.user.id,
        payload.deployment_id,
        _idempotency_key(idempotency_key),
        correlation_id(request),
    )
    AuditService(session, crypto).record(
        "website.rollback_requested",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="deployment",
        target_id=str(deployment.id),
        reason="ROLLBACK_REQUESTED",
        ip_address=request_ip(request, settings),
        metadata={
            "website_id": str(website_id),
            "target_deployment_id": str(payload.deployment_id),
        },
    )
    await session.commit()
    await session.refresh(deployment)
    return _deployment_response(deployment)
