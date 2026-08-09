from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_engine
from zylora_api.db.template_models import Template, TemplateCategory, TemplateTag, TemplateVersion
from zylora_api.db.website_models import Website, WebsitePage
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.fixtures import CURATED_CATALOG
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.websites.service import WebsiteService, resolve_page_path


def multipage_document(count: int) -> dict[str, object]:
    document = deepcopy(CURATED_CATALOG[0]["document"])
    source = deepcopy(document["pages"][0])  # type: ignore[index]
    pages: list[dict[str, object]] = []
    for index in range(count):
        page = deepcopy(source)
        page_id = "home-page" if index == 0 else f"page-{index}"
        parent_id = None if index == 0 else ("page-1" if index > 1 and index % 3 else None)
        page.update(
            {
                "id": page_id,
                "slug": "home" if index == 0 else f"page-{index}",
                "label": "Home" if index == 0 else f"Page {index}",
                "parent_page_id": parent_id,
                "sort_order": index,
                "is_home": index == 0,
                "show_in_navigation": index < 12,
                "status": "ACTIVE",
            }
        )
        page["seo"] = {
            "title": f"Page {index}",
            "description": f"Independent content for page {index}.",
        }
        for component_index, component in enumerate(page["components"]):  # type: ignore[union-attr]
            component["id"] = f"p{index}-{component_index}"
            if component["type"] == "HERO":
                component["props"]["heading"] = f"Page {index}"
        pages.append(page)
    document["pages"] = pages
    return document


@pytest.mark.integration
async def test_template_selection_creates_isolated_thirty_page_drafts_without_plan() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    slug = f"phase4-site-{uuid4()}"
    category_slug = f"{slug}-category"
    tag_slug = f"{slug}-tag"
    emails = [f"{slug}-{index}@example.com" for index in range(2)]
    crypto = AuthCrypto("phase4-instantiation-secret-long-enough")
    async with factory() as session:
        owners = [
            User(
                account_type="USER",
                normalized_email=email,
                display_email=email,
                status="ACTIVE",
                verified_at=datetime.now(UTC),
            )
            for email in emails
        ]
        session.add_all(owners)
        await session.flush()
        template_service = TemplateService(session, crypto)
        payload = TemplateCreateRequest(
            slug=slug,
            name="Thirty Page Agency",
            summary="A complete hierarchical agency site.",
            category_slug=category_slug,
            category_name="Agency",
            category_description="Large professional websites.",
            tags=[tag_slug],
            featured_order=90,
        )
        template = await template_service.create(payload, owners[0].id)
        source_document = multipage_document(30)
        version = await template_service.add_version(template.id, source_document, owners[0].id)
        assert (await template_service.validate(template.id, 1, owners[0].id)).status == "VALIDATED"
        await template_service.approve(template.id, 1)
        await template_service.publish(template.id, 1)
        website_service = WebsiteService(session)
        first = await website_service.instantiate(slug, owners[0].id)
        second = await website_service.instantiate(slug, owners[0].id)
        other = await website_service.instantiate(slug, owners[1].id)
        await session.commit()

        first_pages = await website_service.pages(first.id)
        second_pages = await website_service.pages(second.id)
        assert first.status == second.status == other.status == "DRAFT"
        assert len(first_pages) == len(second_pages) == 30
        assert {page.id for page in first_pages}.isdisjoint({page.id for page in second_pages})
        assert {str(page.id) for page in first_pages}.isdisjoint(
            {str(page["id"]) for page in source_document["pages"]}
        )  # type: ignore[index]
        first_map = {page.id: page for page in first_pages}
        nested = next(page for page in first_pages if page.source_template_page_id == "page-2")
        assert nested.parent_page_id is not None
        assert resolve_page_path(nested, first_map) == "/page-1/page-2"
        assert sum(page.is_home for page in first_pages) == 1
        assert next(page for page in first_pages if page.is_home).slug == ""
        assert len(await website_service.list_for_owner(owners[0].id)) == 2
        with pytest.raises(AuthProblem) as unauthorized:
            await website_service.get_for_owner(first.id, owners[1].id)
        assert unauthorized.value.code == "website_not_found"

        first_pages[1].content["components"][0]["props"]["brand"] = "Changed only here"  # type: ignore[index]
        await session.commit()
        persisted_source = await session.get(TemplateVersion, version.id)
        assert persisted_source is not None and persisted_source.document == source_document
        other_pages = await website_service.pages(other.id)
        assert "Changed only here" not in str(other_pages[1].content)

        with pytest.raises(AuthProblem) as cross_parent:
            await website_service.validate_parent(first_pages[1], other_pages[1].id)
        assert cross_parent.value.code == "cross_website_parent"
        first_pages[1].parent_page_id = first_pages[2].id
        with pytest.raises(AuthProblem) as cycle:
            await website_service.validate_parent(first_pages[2], first_pages[1].id)
        assert cycle.value.code == "page_hierarchy_cycle"
        first_pages[1].parent_page_id = None

        async with session.begin_nested():
            session.add(
                WebsitePage(
                    website_id=first.id,
                    source_template_page_id="duplicate-home",
                    name="Second Home",
                    slug="",
                    sort_order=999,
                    is_home=True,
                    show_in_navigation=True,
                    status="DRAFT",
                    content={"components": []},
                    seo={},
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()

        await session.execute(
            delete(Website).where(Website.id.in_([first.id, second.id, other.id]))
        )
        await session.execute(delete(Template).where(Template.id == template.id))
        await session.execute(delete(TemplateTag).where(TemplateTag.slug == tag_slug))
        await session.execute(
            delete(TemplateCategory).where(TemplateCategory.slug == category_slug)
        )
        await session.execute(delete(User).where(User.id.in_([owner.id for owner in owners])))
        await session.commit()
