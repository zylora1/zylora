from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.lead_models import Notification
from zylora_api.db.session import get_session
from zylora_api.modules.analytics.schemas import (
    AnalyticsDashboardResponse,
    AnalyticsPointResponse,
    NotificationPageResponse,
    NotificationResponse,
)
from zylora_api.modules.analytics.service import AnalyticsService, DashboardMetrics
from zylora_api.modules.auth.http import (
    RequestIdentity,
    get_crypto,
    get_user_identity,
    require_csrf,
    require_json_origin,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.notifications.service import NotificationService

router = APIRouter(prefix="/api/v1", tags=["analytics-and-notifications"])


def dashboard_response(metrics: DashboardMetrics) -> AnalyticsDashboardResponse:
    return AnalyticsDashboardResponse(
        website_id=metrics.website_id,
        timezone=metrics.timezone,
        period_days=metrics.period_days,
        has_published_website=metrics.has_published_website,
        has_meaningful_data=metrics.has_meaningful_data,
        page_views=metrics.page_views,
        sessions=metrics.sessions,
        visitors=metrics.visitors,
        leads=metrics.leads,
        form_leads=metrics.form_leads,
        chatbot_leads=metrics.chatbot_leads,
        chatbot_conversations=metrics.chatbot_conversations,
        chatbot_messages=metrics.chatbot_messages,
        conversions=metrics.conversions,
        points=[
            AnalyticsPointResponse(
                date=item.bucket_date,
                page_views=item.page_views,
                sessions=item.sessions,
                visitors=item.visitors,
                leads=item.leads,
                form_leads=item.form_leads,
                chatbot_leads=item.chatbot_leads,
                chatbot_conversations=item.chatbot_conversations,
                chatbot_messages=item.chatbot_messages,
                conversions=item.conversions,
            )
            for item in metrics.points
        ],
    )


def notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        href=notification.deep_link,
        state=notification.state,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


@router.get("/analytics", response_model=AnalyticsDashboardResponse)
async def analytics_dashboard(
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    website_id: UUID | None = None,
    period_days: Annotated[int, Query()] = 30,
) -> AnalyticsDashboardResponse:
    metrics = await AnalyticsService(session).dashboard(
        owner_user_id=identity.user.id,
        timezone=identity.user.timezone,
        period_days=period_days,
        website_id=website_id,
    )
    await session.commit()
    return dashboard_response(metrics)


@router.get("/notifications", response_model=NotificationPageResponse)
async def notifications(
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before: datetime | None = None,
) -> NotificationPageResponse:
    records, unread_count, next_cursor = await NotificationService(session).page_for_user(
        recipient_user_id=identity.user.id,
        limit=limit,
        before=before,
    )
    await session.commit()
    return NotificationPageResponse(
        notifications=[notification_response(item) for item in records],
        unread_count=unread_count,
        next_cursor=next_cursor,
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> NotificationResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    notification = await NotificationService(session).mark_read(notification_id, identity.user.id)
    await session.commit()
    return notification_response(notification)
