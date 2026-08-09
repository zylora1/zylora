from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
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
from zylora_api.modules.websites.schemas import (
    InstantiateRequest,
    WebsiteListResponse,
    WebsitePageResponse,
    WebsiteResponse,
)
from zylora_api.modules.websites.service import WebsiteService, resolve_page_path

router = APIRouter(prefix="/api/v1", tags=["websites"])


async def response(service: WebsiteService, website: Website) -> WebsiteResponse:
    pages = await service.pages(website.id)
    page_map = {page.id: page for page in pages}
    return WebsiteResponse(
        id=website.id,
        owner_user_id=website.owner_user_id,
        source_template_version_id=website.source_template_version_id,
        display_name=website.display_name,
        status=website.status,
        pages=[
            WebsitePageResponse(
                id=page.id,
                parent_page_id=page.parent_page_id,
                name=page.name,
                slug=page.slug,
                path=resolve_page_path(page, page_map),
                sort_order=page.sort_order,
                is_home=page.is_home,
                show_in_navigation=page.show_in_navigation,
                status=page.status,
            )
            for page in pages
        ],
        created_at=website.created_at,
        updated_at=website.updated_at,
    )


@router.get("/websites", response_model=WebsiteListResponse)
async def list_websites(
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WebsiteListResponse:
    service = WebsiteService(session)
    items = [
        await response(service, website)
        for website in await service.list_for_owner(identity.user.id)
    ]
    await session.commit()
    return WebsiteListResponse(items=items)


@router.get("/websites/{website_id}", response_model=WebsiteResponse)
async def website_detail(
    website_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WebsiteResponse:
    service = WebsiteService(session)
    result = await response(service, await service.get_for_owner(website_id, identity.user.id))
    await session.commit()
    return result


@router.post(
    "/templates/{slug}/instantiate",
    response_model=WebsiteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def instantiate(
    slug: str,
    payload: InstantiateRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> WebsiteResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    service = WebsiteService(session)
    website = await service.instantiate(slug, identity.user.id)
    AuditService(session, crypto).record(
        "website.instantiated_from_template",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website",
        target_id=str(website.id),
        reason="TEMPLATE_SELECTED",
        ip_address=request_ip(request, settings),
        metadata={
            "template_slug": slug,
            "source_template_version_id": str(website.source_template_version_id),
        },
    )
    result = await response(service, website)
    await session.commit()
    return result
