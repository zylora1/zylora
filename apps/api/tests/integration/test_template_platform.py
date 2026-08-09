from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker
from zylora_api.app import create_app
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_engine
from zylora_api.db.template_models import Template, TemplateCategory, TemplateTag
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.fixtures import CURATED_CATALOG
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService


@pytest.mark.integration
async def test_template_lifecycle_exposes_only_current_published_version() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    slug = f"phase4-{uuid4()}"
    email = f"{slug}@example.com"
    crypto = AuthCrypto("phase4-integration-secret-long-enough")
    async with factory() as session:
        actor = User(
            account_type="USER",
            normalized_email=email,
            display_email=email,
            status="ACTIVE",
            verified_at=datetime.now(UTC),
        )
        session.add(actor)
        await session.flush()
        service = TemplateService(session, crypto)
        fixture = CURATED_CATALOG[0]
        payload = TemplateCreateRequest.model_validate(
            {**{key: value for key, value in fixture.items() if key != "document"}, "slug": slug}
        )
        template = await service.create(payload, actor.id)
        version = await service.add_version(template.id, deepcopy(fixture["document"]), actor.id)  # type: ignore[arg-type]
        await session.commit()

        app = create_app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            hidden = await client.get(f"/api/v1/templates/{slug}")
        assert hidden.status_code == 404

        validated = await service.validate(template.id, version.version, actor.id)
        assert validated.status == "VALIDATED"
        await service.approve(template.id, version.version)
        published = await service.publish(template.id, version.version)
        await session.commit()
        assert published.status == "PUBLISHED"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            listed = await client.get(
                "/api/v1/templates",
                params={"query": "Haven", "category": fixture["category_slug"], "tag": "clinic"},
            )
            detail = await client.get(f"/api/v1/templates/{slug}")
            preview = await client.get(f"/api/v1/templates/{slug}/versions/1/preview")
        assert listed.status_code == detail.status_code == preview.status_code == 200
        assert [item["slug"] for item in listed.json()["items"]] == [slug]
        assert preview.json()["document"]["schema_version"] == "1.0.0"

        await service.deprecate(template.id, 1)
        await session.commit()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            assert (await client.get(f"/api/v1/templates/{slug}")).status_code == 404

        await session.execute(delete(Template).where(Template.id == template.id))
        await session.execute(delete(TemplateTag).where(TemplateTag.slug.in_(fixture["tags"])))
        await session.execute(
            delete(TemplateCategory).where(TemplateCategory.slug == fixture["category_slug"])
        )
        await session.execute(delete(User).where(User.id == actor.id))
        await session.commit()


@pytest.mark.integration
async def test_stale_or_rejected_validation_cannot_be_approved() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    slug = f"phase4-invalid-{uuid4()}"
    email = f"{slug}@example.com"
    crypto = AuthCrypto("phase4-integration-secret-long-enough")
    async with factory() as session:
        actor = User(
            account_type="USER",
            normalized_email=email,
            display_email=email,
            status="ACTIVE",
            verified_at=datetime.now(UTC),
        )
        session.add(actor)
        await session.flush()
        fixture = CURATED_CATALOG[1]
        service = TemplateService(session, crypto)
        payload = TemplateCreateRequest.model_validate(
            {**{key: value for key, value in fixture.items() if key != "document"}, "slug": slug}
        )
        template = await service.create(payload, actor.id)
        invalid = deepcopy(fixture["document"])
        invalid["requirements"] = ["UNVERIFIED_CAPABILITY"]  # type: ignore[index]
        await service.add_version(template.id, invalid, actor.id)  # type: ignore[arg-type]
        rejected = await service.validate(template.id, 1, actor.id)
        assert rejected.status == "REJECTED"
        with pytest.raises(AuthProblem) as caught:
            await service.approve(template.id, 1)
        assert caught.value.code == "validation_stale"
        await session.rollback()
