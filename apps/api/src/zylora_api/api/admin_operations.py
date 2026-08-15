from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.api.health import ReadinessService, get_readiness_service
from zylora_api.core.config import Settings, get_settings
from zylora_api.db.session import get_session
from zylora_api.modules.admin.operations import AdminOperationsService, AdminSection
from zylora_api.modules.admin.schemas import (
    AdminFunnelStep,
    AdminGrowthResponse,
    AdminHealthResponse,
    AdminOperationListResponse,
    AdminOverviewResponse,
    AdminRetentionMetric,
    AdminUserDetail,
    AdminUserListResponse,
)
from zylora_api.modules.analytics.activation import ProductAnalyticsService
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.http import (
    RequestIdentity,
    correlation_id,
    get_admin_identity,
    get_crypto,
    request_ip,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.service import problem

router = APIRouter(prefix="/api/v1/admin", tags=["super-admin-operations"])


@router.get("/overview", response_model=AdminOverviewResponse)
async def overview(
    _: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AdminOverviewResponse:
    result = await AdminOperationsService(session).overview()
    await session.commit()
    return result


@router.get("/analytics/growth", response_model=AdminGrowthResponse)
async def growth_analytics(
    _: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    period_days: Annotated[int | None, Query()] = 30,
) -> AdminGrowthResponse:
    result = await ProductAnalyticsService(session).admin_growth(period_days)
    await session.commit()
    return AdminGrowthResponse(
        range_days=result.range_days,
        funnel=[AdminFunnelStep(**vars(item)) for item in result.funnel],
        active_value_sites_30d=result.active_value_sites_30d,
        previous_active_value_sites_30d=result.previous_active_value_sites_30d,
        active_value_sites_change_percent=result.active_value_sites_change_percent,
        retention=[AdminRetentionMetric(**vars(item)) for item in result.retention],
        published_with_first_lead=result.published_with_first_lead,
        published_with_zero_leads=result.published_with_zero_leads,
        paid_with_first_lead=result.paid_with_first_lead,
        paid_with_zero_leads=result.paid_with_zero_leads,
        subscription_state_counts=result.subscription_state_counts,
    )


@router.get("/users", response_model=AdminUserListResponse)
async def users(
    _: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    query: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AdminUserListResponse:
    result = await AdminOperationsService(session).users(query, limit)
    await session.commit()
    return result


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user_detail(
    user_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> AdminUserDetail:
    result = await AdminOperationsService(session).user_detail(user_id)
    if not result:
        raise problem(404, "user_not_found", "User not found.")
    AuditService(session, crypto).record(
        "admin.user_viewed",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="user",
        target_id=str(user_id),
        reason="SUPER_ADMIN_USER_OPERATIONS_READ",
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    return result


@router.get("/operations/{section}", response_model=AdminOperationListResponse)
async def operation_list(
    section: AdminSection,
    _: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AdminOperationListResponse:
    result = await AdminOperationsService(session).section(section, limit)
    await session.commit()
    return result


@router.get("/health", response_model=AdminHealthResponse)
async def admin_health(
    _: Annotated[RequestIdentity, Depends(get_admin_identity)],
    service: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> AdminHealthResponse:
    current_status, checks = await service.evaluate()
    return AdminHealthResponse(
        status=current_status,
        checks=checks,
        observed_at=datetime.now(UTC),
    )
