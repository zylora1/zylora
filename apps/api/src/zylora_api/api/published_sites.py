from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.deployment_models import Deployment, Domain
from zylora_api.db.session import get_session
from zylora_api.db.website_models import Website
from zylora_api.modules.publishing.runtime import publication_storage_for

router = APIRouter(tags=["published-site"])


def _hostname(request: Request) -> str:
    hostname = request.url.hostname
    if not hostname:
        raise HTTPException(status_code=404, detail="Published Website not found.")
    return hostname.casefold()


async def _domain_for_host(session: AsyncSession, hostname: str) -> Domain:
    domain = await session.scalar(
        select(Domain).where(
            Domain.hostname == hostname,
            Domain.state.in_(("PROVISIONING", "ACTIVE", "DEGRADED")),
        )
    )
    if not domain:
        raise HTTPException(status_code=404, detail="Published Website not found.")
    return domain


async def _deployment_for_health(session: AsyncSession, domain: Domain) -> Deployment:
    deployment = await session.scalar(
        select(Deployment)
        .where(
            Deployment.domain_id == domain.id,
            Deployment.state.in_(
                ("HEALTH_CHECKING", "SWITCHING", "ACTIVE", "SUPERSEDED", "ROLLING_BACK")
            ),
        )
        .order_by(Deployment.queued_at.desc())
    )
    if not deployment:
        raise HTTPException(status_code=503, detail="Deployment is not ready.")
    return deployment


@router.get("/_zylora/health", include_in_schema=False)
async def published_health(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    domain = await _domain_for_host(session, _hostname(request))
    deployment = await _deployment_for_health(session, domain)
    return Response(
        status_code=200,
        content="ok",
        media_type="text/plain",
        headers={"X-Zylora-Deployment": str(deployment.id), "Cache-Control": "no-store"},
    )


async def _active_deployment(session: AsyncSession, domain: Domain) -> Deployment:
    website = await session.scalar(
        select(Website).where(
            Website.id == domain.website_id,
            Website.status == "PUBLISHED",
            Website.active_deployment_id.is_not(None),
        )
    )
    if not website or not website.active_deployment_id:
        raise HTTPException(status_code=404, detail="Published Website not found.")
    deployment = await session.get(Deployment, website.active_deployment_id)
    if not deployment or deployment.domain_id != domain.id or deployment.state != "ACTIVE":
        raise HTTPException(status_code=404, detail="Published Website not found.")
    return deployment


def _path(value: str) -> str:
    normalized = "/" + value.strip("/")
    return "/" if normalized == "/" else normalized


@router.get("/{public_path:path}", include_in_schema=False)
async def published_page(
    public_path: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    domain = await _domain_for_host(session, _hostname(request))
    deployment = await _active_deployment(session, domain)
    if not deployment.artifact_key:
        raise HTTPException(status_code=503, detail="Published artifact is unavailable.")
    storage = publication_storage_for(settings)
    try:
        manifest_bytes = await run_in_threadpool(storage.get_bytes, deployment.artifact_key)
        manifest: dict[str, Any] = json.loads(manifest_bytes)
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=503, detail="Published artifact is unavailable.") from error
    path = _path(public_path)
    redirects = manifest.get("redirects")
    if isinstance(redirects, dict) and isinstance(redirects.get(path), str):
        return RedirectResponse(url=redirects[path], status_code=308)
    files = manifest.get("files")
    key = files.get(path) if isinstance(files, dict) else None
    if not isinstance(key, str):
        raise HTTPException(status_code=404, detail="Published page not found.")
    try:
        body = await run_in_threadpool(storage.get_bytes, key)
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        raise HTTPException(status_code=503, detail="Published artifact is unavailable.") from error
    return HTMLResponse(
        content=body,
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Zylora-Deployment": str(deployment.id),
            "Cache-Control": "public, max-age=60",
        },
    )
