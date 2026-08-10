from __future__ import annotations

from typing import Annotated
from uuid import UUID

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
from zylora_api.modules.blog.schemas import (
    BlogPostRequest,
    BlogPostResponse,
    BlogReasonRequest,
    BlogScheduleRequest,
    BlogSitemapItem,
    PublicBlogPostResponse,
)
from zylora_api.modules.blog.service import BlogPostSummary, BlogService

router = APIRouter(prefix="/api/v1", tags=["blog"])


def _command(
    request: Request, identity: RequestIdentity, settings: Settings, crypto: AuthCrypto
) -> None:
    require_json_origin(request, settings, admin=True)
    require_csrf(request, identity, crypto)


def _response(row: BlogPostSummary) -> BlogPostResponse:
    return BlogPostResponse(**row.__dict__)


@router.get("/admin/blog/posts", response_model=list[BlogPostResponse])
async def admin_posts(
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[BlogPostResponse]:
    return [_response(row) for row in await BlogService(session).list_admin()]


@router.post(
    "/admin/blog/posts", response_model=BlogPostResponse, status_code=status.HTTP_201_CREATED
)
async def create_post(
    payload: BlogPostRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> BlogPostResponse:
    _command(request, identity, settings, crypto)
    service = BlogService(session)
    post = await service.create(actor_user_id=identity.user.id, payload=payload.model_dump())
    summary = await service.summary(post)
    AuditService(session, crypto).record(
        "blog.post_created",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="blog_post",
        target_id=str(post.id),
        reason="SUPER_ADMIN_BLOG_CREATE",
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    return _response(summary)


@router.patch("/admin/blog/posts/{post_id}", response_model=BlogPostResponse)
async def update_post(
    post_id: UUID,
    payload: BlogPostRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> BlogPostResponse:
    _command(request, identity, settings, crypto)
    service = BlogService(session)
    post = await service.update(post_id, payload=payload.model_dump())
    summary = await service.summary(post)
    AuditService(session, crypto).record(
        "blog.post_updated",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="blog_post",
        target_id=str(post.id),
        reason="SUPER_ADMIN_BLOG_UPDATE",
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    return _response(summary)


async def _transition(
    action: str,
    post_id: UUID,
    payload: BlogReasonRequest,
    request: Request,
    identity: RequestIdentity,
    session: AsyncSession,
    settings: Settings,
    crypto: AuthCrypto,
) -> BlogPostResponse:
    _command(request, identity, settings, crypto)
    service = BlogService(session)
    post = await (
        service.publish(post_id, correlation_id=correlation_id(request))
        if action == "publish"
        else getattr(service, action)(post_id)
    )
    summary = await service.summary(post)
    AuditService(session, crypto).record(
        f"blog.post_{action}",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="blog_post",
        target_id=str(post.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
        metadata={"outcome": post.state},
    )
    await session.commit()
    return _response(summary)


@router.post("/admin/blog/posts/{post_id}/ready", response_model=BlogPostResponse)
async def ready_post(
    post_id: UUID,
    payload: BlogReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> BlogPostResponse:
    return await _transition(
        "ready", post_id, payload, request, identity, session, settings, crypto
    )


@router.post("/admin/blog/posts/{post_id}/publish", response_model=BlogPostResponse)
async def publish_post(
    post_id: UUID,
    payload: BlogReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> BlogPostResponse:
    return await _transition(
        "publish", post_id, payload, request, identity, session, settings, crypto
    )


@router.post("/admin/blog/posts/{post_id}/unpublish", response_model=BlogPostResponse)
async def unpublish_post(
    post_id: UUID,
    payload: BlogReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> BlogPostResponse:
    return await _transition(
        "unpublish", post_id, payload, request, identity, session, settings, crypto
    )


@router.post("/admin/blog/posts/{post_id}/schedule", response_model=BlogPostResponse)
async def schedule_post(
    post_id: UUID,
    payload: BlogScheduleRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> BlogPostResponse:
    _command(request, identity, settings, crypto)
    service = BlogService(session)
    post = await service.schedule(post_id, payload.scheduled_at)
    summary = await service.summary(post)
    AuditService(session, crypto).record(
        "blog.post_scheduled",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="blog_post",
        target_id=str(post.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
        metadata={"scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None},
    )
    await session.commit()
    return _response(summary)


@router.get("/blog/posts", response_model=list[BlogPostResponse])
async def public_posts(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[BlogPostResponse]:
    return [_response(row) for row in await BlogService(session).public_list()]


@router.get("/blog/posts/{slug}", response_model=PublicBlogPostResponse)
async def public_post(
    slug: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> PublicBlogPostResponse:
    service = BlogService(session)
    post = await service.public_get(slug)
    summary = await service.summary(post)
    return PublicBlogPostResponse(
        **summary.__dict__,
        content_html=service.render_html(post.content),
        featured_image_url=post.featured_image_url,
        seo_title=post.seo_title,
        meta_description=post.meta_description,
        canonical_path=f"/blog/{post.slug}",
        og_title=post.og_title,
        og_description=post.og_description,
    )


@router.get("/blog/sitemap", response_model=list[BlogSitemapItem])
async def blog_sitemap(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[BlogSitemapItem]:
    rows = await BlogService(session).public_list(limit=10_000)
    return [
        BlogSitemapItem(slug=row.slug, published_at=row.published_at)
        for row in rows
        if row.published_at
    ]
