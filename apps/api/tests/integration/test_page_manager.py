from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_engine
from zylora_api.db.template_models import Template, TemplateCategory, TemplateTag
from zylora_api.db.website_models import Website, WebsitePagePathChange
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.fixtures import CURATED_CATALOG
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.websites.schemas import PageCreateRequest, PageUpdateRequest
from zylora_api.modules.websites.service import WebsiteService, build_navigation, page_paths


def large_document(count: int) -> dict[str, object]:
    document = deepcopy(CURATED_CATALOG[0]["document"])
    source = deepcopy(document["pages"][0])  # type: ignore[index]
    pages: list[dict[str, object]] = []
    for index in range(count):
        page = deepcopy(source)
        page["components"] = [deepcopy(source["components"][1])]
        is_home = index == 0
        root_index = index - ((index - 1) % 10) if index else 0
        page_id = "home" if is_home else f"page-{index}"
        page.update(
            {
                "id": page_id,
                "slug": "home" if is_home else f"page-{index}",
                "label": "Home" if is_home else f"Page {index}",
                "parent_page_id": (None if is_home or index % 10 == 1 else f"page-{root_index}"),
                "sort_order": 0 if is_home else index % 10,
                "is_home": is_home,
                "show_in_navigation": index % 6 != 0,
                "status": "ACTIVE",
                "seo": {
                    "title": "Home" if is_home else f"Page {index}",
                    "description": f"Page {index} description.",
                },
            }
        )
        for component_index, component in enumerate(page["components"]):  # type: ignore[union-attr]
            component["id"] = f"p{index}-{component_index}"
        pages.append(page)
    document["pages"] = pages
    document["features"] = []
    document["requirements"] = []
    return document


@pytest.mark.integration
async def test_page_manager_mutations_scale_persist_and_remain_plan_free() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    unique = uuid4().hex
    slug = f"phase5-{unique}"
    category_slug = f"phase5-category-{unique}"
    tag_slug = f"phase5-tag-{unique}"
    emails = [f"phase5-{unique}-{index}@example.com" for index in range(2)]
    crypto = AuthCrypto("phase5-page-manager-secret-long-enough")
    async with factory() as session:
        users = [
            User(
                account_type="USER",
                normalized_email=email,
                display_email=email,
                status="ACTIVE",
                verified_at=datetime.now(UTC),
            )
            for email in emails
        ]
        session.add_all(users)
        await session.flush()
        template_service = TemplateService(session, crypto)
        template = await template_service.create(
            TemplateCreateRequest(
                slug=slug,
                name="Hundred Page Directory",
                summary="A large hierarchical Website used to verify Page Manager scale.",
                category_slug=category_slug,
                category_name="Directory",
                category_description="Large structured Websites.",
                tags=[tag_slug],
                featured_order=100,
            ),
            users[0].id,
        )
        await template_service.add_version(template.id, large_document(100), users[0].id)
        validation = await template_service.validate(template.id, 1, users[0].id)
        assert validation.status == "VALIDATED", validation.validation_summary
        await template_service.approve(template.id, 1)
        await template_service.publish(template.id, 1)

        service = WebsiteService(session)
        website = await service.instantiate(slug, users[0].id)
        second_draft = await service.instantiate(slug, users[0].id)
        other_draft = await service.instantiate(slug, users[1].id)
        await session.commit()

        pages = await service.pages(website.id)
        assert len(pages) == 100
        assert len(await service.list_for_owner(users[0].id)) == 2
        paths = page_paths(pages)
        template_child = next(page for page in pages if page.source_template_page_id == "page-2")
        assert paths[template_child.id] == "/page-1/page-2"
        assert build_navigation(pages)

        added = await service.add_page(
            website.id,
            users[0].id,
            PageCreateRequest(
                name="Campaign Summer",
                slug="summer",
                parent_page_id=None,
                sort_order=99,
                show_in_navigation=False,
                status="DRAFT",
                seo={},
            ),
        )
        assert len(await service.pages(website.id)) == 101
        assert added.website.status == "DRAFT"

        pages = await service.pages(website.id)
        page_two = next(page for page in pages if page.source_template_page_id == "page-2")
        page_three = next(page for page in pages if page.source_template_page_id == "page-3")
        moved = await service.update_page(
            website.id,
            page_two.id,
            users[0].id,
            PageUpdateRequest(
                name="SEO Services",
                slug="seo-services",
                parent_page_id=page_three.id,
                sort_order=0,
                show_in_navigation=False,
                seo={"title": "SEO Services", "description": "Technical SEO services."},
            ),
        )
        assert moved.path_changes
        assert moved.path_changes[0].old_path == "/page-1/page-2"
        assert moved.path_changes[0].new_path == "/page-1/page-3/seo-services"
        pages = await service.pages(website.id)
        assert page_paths(pages)[page_two.id] == "/page-1/page-3/seo-services"
        assert all(node["page_id"] != page_two.id for node in build_navigation(pages))
        history = list(
            (
                await session.scalars(
                    select(WebsitePagePathChange).where(
                        WebsitePagePathChange.website_id == website.id,
                        WebsitePagePathChange.page_id == page_two.id,
                    )
                )
            ).all()
        )
        assert history and history[-1].new_path == "/page-1/page-3/seo-services"

        page_four = next(page for page in pages if page.source_template_page_id == "page-4")
        original_slug = page_four.slug
        with pytest.raises(AuthProblem) as duplicate:
            await service.update_page(
                website.id,
                page_four.id,
                users[0].id,
                PageUpdateRequest(slug="page-5"),
            )
        assert duplicate.value.code == "duplicate_page_slug"
        page_four.slug = original_slug

        with pytest.raises(AuthProblem) as invalid:
            await service.update_page(
                website.id,
                page_four.id,
                users[0].id,
                PageUpdateRequest(slug="Invalid Slug"),
            )
        assert invalid.value.code == "invalid_page_slug"

        original_three_parent = page_three.parent_page_id
        with pytest.raises(AuthProblem) as cycle:
            await service.update_page(
                website.id,
                page_three.id,
                users[0].id,
                PageUpdateRequest(parent_page_id=page_two.id),
            )
        assert cycle.value.code == "page_hierarchy_cycle"
        page_three.parent_page_id = original_three_parent

        other_page = (await service.pages(other_draft.id))[1]
        with pytest.raises(AuthProblem) as cross_website:
            await service.update_page(
                website.id,
                page_four.id,
                users[0].id,
                PageUpdateRequest(parent_page_id=other_page.id),
            )
        assert cross_website.value.code == "cross_website_parent"

        home = next(page for page in pages if page.is_home)
        with pytest.raises(AuthProblem) as protected_home:
            await service.delete_page(website.id, home.id, users[0].id)
        assert protected_home.value.code == "home_page_delete_forbidden"

        with pytest.raises(AuthProblem) as unauthorized:
            await service.add_page(
                website.id,
                users[1].id,
                PageCreateRequest(
                    name="Unauthorized",
                    slug="unauthorized",
                    show_in_navigation=False,
                ),
            )
        assert unauthorized.value.code == "website_not_found"

        deleted_parent = await service.delete_page(website.id, page_three.id, users[0].id)
        assert any(change.page_id == page_two.id for change in deleted_parent.path_changes)
        pages = await service.pages(website.id)
        assert page_paths(pages)[page_two.id] == "/page-1/seo-services"
        assert page_two.parent_page_id is not None
        await session.commit()

        await session.execute(
            delete(Website).where(Website.id.in_([website.id, second_draft.id, other_draft.id]))
        )
        await session.execute(delete(Template).where(Template.id == template.id))
        await session.execute(delete(TemplateTag).where(TemplateTag.slug == tag_slug))
        await session.execute(
            delete(TemplateCategory).where(TemplateCategory.slug == category_slug)
        )
        await session.execute(delete(User).where(User.id.in_([user.id for user in users])))
        await session.commit()
