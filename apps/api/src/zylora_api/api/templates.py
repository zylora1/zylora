from __future__ import annotations

import hashlib
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.session import get_session
from zylora_api.db.template_models import (
    Template,
    TemplateAsset,
    TemplateCategory,
    TemplateTag,
    TemplateTagAssignment,
    TemplateVersion,
)
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
from zylora_api.modules.templates.assets import (
    AssetUploadRequest,
    asset_key,
    get_object_storage,
    process_raster,
)
from zylora_api.modules.templates.schemas import (
    AdminTemplateListResponse,
    AdminTemplateResponse,
    CatalogResponse,
    PreviewResponse,
    ReasonRequest,
    TemplateCreateRequest,
    TemplateMetadataUpdateRequest,
    TemplateSummary,
    VersionCreateRequest,
    VersionResponse,
)
from zylora_api.modules.templates.service import TemplateService, problem
from zylora_api.storage.base import ObjectStorage

router = APIRouter(prefix="/api/v1", tags=["templates"])


async def _tags(session: AsyncSession, template_id: UUID) -> list[str]:
    return list(
        (
            await session.scalars(
                select(TemplateTag.slug)
                .join(TemplateTagAssignment, TemplateTagAssignment.tag_id == TemplateTag.id)
                .where(TemplateTagAssignment.template_id == template_id)
                .order_by(TemplateTag.slug)
            )
        ).all()
    )


def _version_response(version: TemplateVersion) -> VersionResponse:
    return VersionResponse(
        id=version.id,
        version=version.version,
        status=version.status,
        checksum=version.checksum,
        validation_summary=version.validation_summary,
        created_at=version.created_at,
    )


@router.get("/templates", response_model=CatalogResponse)
async def catalog(
    session: Annotated[AsyncSession, Depends(get_session)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    query: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    tag: Annotated[str | None, Query(max_length=80)] = None,
    feature: Annotated[str | None, Query(max_length=60)] = None,
    sort: Annotated[str, Query(pattern="^(featured|name)$")] = "featured",
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
    limit: Annotated[int, Query(ge=1, le=48)] = 24,
) -> CatalogResponse:
    fingerprint = hashlib.sha256(
        json.dumps([query, category, tag, feature, sort], separators=(",", ":")).encode()
    ).hexdigest()
    service = TemplateService(session, crypto)
    offset = service.decode_cursor(cursor, fingerprint)
    statement = (
        select(Template, TemplateVersion, TemplateCategory)
        .join(TemplateVersion, Template.current_published_version_id == TemplateVersion.id)
        .join(TemplateCategory, Template.category_id == TemplateCategory.id)
        .where(
            Template.status == "ACTIVE",
            TemplateVersion.status == "PUBLISHED",
            TemplateCategory.active.is_(True),
        )
    )
    if query:
        statement = statement.where(
            Template.name.ilike(f"%{query}%") | Template.summary.ilike(f"%{query}%")
        )
    if category:
        statement = statement.where(TemplateCategory.slug == category)
    if tag:
        statement = statement.where(
            exists(
                select(TemplateTagAssignment.template_id)
                .join(TemplateTag, TemplateTag.id == TemplateTagAssignment.tag_id)
                .where(TemplateTagAssignment.template_id == Template.id, TemplateTag.slug == tag)
            )
        )
    if feature:
        statement = statement.where(TemplateVersion.document["features"].contains([feature]))
    statement = (
        statement.order_by(Template.name, Template.id)
        if sort == "name"
        else statement.order_by(Template.featured_order, Template.name, Template.id)
    )
    rows = (await session.execute(statement.offset(offset).limit(limit + 1))).all()
    items = [
        TemplateSummary(
            id=t.id,
            slug=t.slug,
            name=t.name,
            summary=t.summary,
            category=c.name,
            category_slug=c.slug,
            tags=await _tags(session, t.id),
            features=list(v.document.get("features", [])),
            version=v.version,
            status=v.status,
            featured_order=t.featured_order,
        )
        for t, v, c in rows[:limit]
    ]
    return CatalogResponse(
        items=items,
        next_cursor=service.encode_cursor(offset + limit, fingerprint)
        if len(rows) > limit
        else None,
    )


@router.get("/templates/{slug}", response_model=TemplateSummary)
async def detail(
    slug: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> TemplateSummary:
    row = (
        await session.execute(
            select(Template, TemplateVersion, TemplateCategory)
            .join(TemplateVersion, Template.current_published_version_id == TemplateVersion.id)
            .join(TemplateCategory)
            .where(
                Template.slug == slug,
                Template.status == "ACTIVE",
                TemplateVersion.status == "PUBLISHED",
            )
        )
    ).one_or_none()
    if not row:
        raise problem(404, "template_not_found", "Template not found.")
    template, version, category = row
    return TemplateSummary(
        id=template.id,
        slug=template.slug,
        name=template.name,
        summary=template.summary,
        category=category.name,
        category_slug=category.slug,
        tags=await _tags(session, template.id),
        features=list(version.document.get("features", [])),
        version=version.version,
        status=version.status,
        featured_order=template.featured_order,
    )


@router.get("/templates/{slug}/versions/{version}/preview", response_model=PreviewResponse)
async def preview(
    slug: str, version: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> PreviewResponse:
    row = (
        await session.execute(
            select(Template, TemplateVersion)
            .join(TemplateVersion)
            .where(
                Template.slug == slug,
                Template.status == "ACTIVE",
                TemplateVersion.version == version,
                TemplateVersion.status == "PUBLISHED",
                Template.current_published_version_id == TemplateVersion.id,
            )
        )
    ).one_or_none()
    if not row:
        raise problem(404, "template_preview_not_found", "Published Template preview not found.")
    template, model = row
    return PreviewResponse(
        slug=template.slug,
        name=template.name,
        version=model.version,
        document=model.document,
        checksum=model.checksum,
    )


def _admin_command(
    request: Request, identity: RequestIdentity, settings: Settings, crypto: AuthCrypto
) -> None:
    require_json_origin(request, settings, admin=True)
    require_csrf(request, identity, crypto)


@router.get("/admin/templates", response_model=AdminTemplateListResponse)
async def admin_list(
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AdminTemplateListResponse:
    templates = (await session.scalars(select(Template).order_by(Template.updated_at.desc()))).all()
    items = []
    for template in templates:
        category = await session.get(TemplateCategory, template.category_id)
        versions = (
            await session.scalars(
                select(TemplateVersion)
                .where(TemplateVersion.template_id == template.id)
                .order_by(TemplateVersion.version.desc())
            )
        ).all()
        items.append(
            AdminTemplateResponse(
                id=template.id,
                slug=template.slug,
                name=template.name,
                summary=template.summary,
                status=template.status,
                category=category.name if category else "Unknown",
                tags=await _tags(session, template.id),
                versions=[_version_response(item) for item in versions],
            )
        )
    await session.commit()
    return AdminTemplateListResponse(items=items)


@router.post(
    "/admin/templates", response_model=AdminTemplateResponse, status_code=status.HTTP_201_CREATED
)
async def admin_create(
    payload: TemplateCreateRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> AdminTemplateResponse:
    _admin_command(request, identity, settings, crypto)
    template = await TemplateService(session, crypto).create(payload, identity.user.id)
    AuditService(session, crypto).record(
        "template.created",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="template",
        target_id=str(template.id),
        reason="CREATE_TEMPLATE",
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    return AdminTemplateResponse(
        id=template.id,
        slug=template.slug,
        name=template.name,
        summary=template.summary,
        status=template.status,
        category=payload.category_name,
        tags=sorted(set(payload.tags)),
        versions=[],
    )


@router.patch("/admin/templates/{template_id}", response_model=AdminTemplateResponse)
async def admin_update_metadata(
    template_id: UUID,
    payload: TemplateMetadataUpdateRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> AdminTemplateResponse:
    _admin_command(request, identity, settings, crypto)
    template = await TemplateService(session, crypto).update_metadata(template_id, payload)
    category = await session.get(TemplateCategory, template.category_id)
    versions = list(
        (
            await session.scalars(
                select(TemplateVersion)
                .where(TemplateVersion.template_id == template.id)
                .order_by(TemplateVersion.version.desc())
            )
        ).all()
    )
    AuditService(session, crypto).record(
        "template.metadata_updated",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="template",
        target_id=str(template.id),
        reason="SUPER_ADMIN_TEMPLATE_METADATA",
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    return AdminTemplateResponse(
        id=template.id,
        slug=template.slug,
        name=template.name,
        summary=template.summary,
        status=template.status,
        category=category.name if category else "Unknown",
        tags=await _tags(session, template.id),
        versions=[_version_response(item) for item in versions],
    )


@router.post(
    "/admin/templates/{template_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_add_version(
    template_id: UUID,
    payload: VersionCreateRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> VersionResponse:
    _admin_command(request, identity, settings, crypto)
    version = await TemplateService(session, crypto).add_version(
        template_id, payload.document, identity.user.id
    )
    AuditService(session, crypto).record(
        "template.version_created",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="template_version",
        target_id=str(version.id),
        reason="CREATE_VERSION",
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    return _version_response(version)


async def _transition(
    action: str,
    template_id: UUID,
    version: int,
    payload: ReasonRequest,
    request: Request,
    identity: RequestIdentity,
    session: AsyncSession,
    settings: Settings,
    crypto: AuthCrypto,
) -> VersionResponse:
    _admin_command(request, identity, settings, crypto)
    service = TemplateService(session, crypto)
    model = (
        await getattr(service, action)(template_id, version, identity.user.id)
        if action == "validate"
        else await getattr(service, action)(template_id, version)
    )
    AuditService(session, crypto).record(
        f"template.{action}",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="template_version",
        target_id=str(model.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
        metadata={"version": version, "outcome": model.status},
    )
    await session.commit()
    return _version_response(model)


@router.post(
    "/admin/templates/{template_id}/versions/{version}/validate", response_model=VersionResponse
)
async def admin_validate(
    template_id: UUID,
    version: int,
    payload: ReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> VersionResponse:
    return await _transition(
        "validate", template_id, version, payload, request, identity, session, settings, crypto
    )


@router.post(
    "/admin/templates/{template_id}/versions/{version}/approve", response_model=VersionResponse
)
async def admin_approve(
    template_id: UUID,
    version: int,
    payload: ReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> VersionResponse:
    return await _transition(
        "approve", template_id, version, payload, request, identity, session, settings, crypto
    )


@router.post(
    "/admin/templates/{template_id}/versions/{version}/publish", response_model=VersionResponse
)
async def admin_publish(
    template_id: UUID,
    version: int,
    payload: ReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> VersionResponse:
    return await _transition(
        "publish", template_id, version, payload, request, identity, session, settings, crypto
    )


@router.post(
    "/admin/templates/{template_id}/versions/{version}/deprecate", response_model=VersionResponse
)
async def admin_deprecate(
    template_id: UUID,
    version: int,
    payload: ReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> VersionResponse:
    return await _transition(
        "deprecate", template_id, version, payload, request, identity, session, settings, crypto
    )


@router.post(
    "/admin/templates/{template_id}/versions/{version}/unpublish", response_model=VersionResponse
)
async def admin_unpublish_template(
    template_id: UUID,
    version: int,
    payload: ReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> VersionResponse:
    return await _transition(
        "unpublish", template_id, version, payload, request, identity, session, settings, crypto
    )


@router.post(
    "/admin/templates/{template_id}/versions/{version}/restore", response_model=VersionResponse
)
async def admin_restore_template(
    template_id: UUID,
    version: int,
    payload: ReasonRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> VersionResponse:
    return await _transition(
        "restore", template_id, version, payload, request, identity, session, settings, crypto
    )


@router.post("/admin/template-assets", status_code=status.HTTP_201_CREATED)
async def admin_asset(
    payload: AssetUploadRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> dict[str, object]:
    _admin_command(request, identity, settings, crypto)
    data, width, height, mime = process_raster(payload)
    key, checksum = asset_key(data)
    storage.put_bytes(key, data, mime)
    asset = TemplateAsset(
        status="READY",
        object_key=key,
        mime_type=mime,
        checksum=checksum,
        width=width,
        height=height,
        byte_size=len(data),
        license=payload.license,
        provenance=payload.provenance,
        processing_policy="RASTER_REENCODE_V1",
        created_by=identity.user.id,
    )
    session.add(asset)
    await session.flush()
    AuditService(session, crypto).record(
        "template.asset_processed",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="template_asset",
        target_id=str(asset.id),
        reason="ASSET_IMPORT",
        ip_address=request_ip(request, settings),
        metadata={"mime": mime, "size": len(data), "checksum": checksum},
    )
    await session.commit()
    return {
        "id": asset.id,
        "status": asset.status,
        "mime_type": mime,
        "width": width,
        "height": height,
        "checksum": checksum,
    }
