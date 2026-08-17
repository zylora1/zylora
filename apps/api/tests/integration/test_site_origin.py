from __future__ import annotations

import pytest
from zylora_api.db.website_models import Website, WebsitePage
from zylora_api.modules.auth.errors import AuthProblem as ApiProblem
from zylora_api.modules.editor.schemas import AddPage
from zylora_api.modules.editor.service import EditorService
from zylora_api.modules.websites.service import WebsiteService


@pytest.mark.integration
@pytest.mark.asyncio
async def test_template_site_origin_page_restriction(
    async_session, sample_user, sample_template_version
):
    # 1. Create a template-origin website
    website = Website(
        owner_user_id=sample_user.id,
        source_template_version_id=sample_template_version.id,
        site_origin="TEMPLATE",
        display_name="Template Site",
        status="DRAFT",
        theme={"color": "blue"},
    )
    async_session.add(website)
    await async_session.flush()

    home_page = WebsitePage(
        website_id=website.id,
        source_template_page_id="p1",
        name="Home",
        slug="",
        is_home=True,
        show_in_navigation=True,
        status="DRAFT",
        content={"components": []},
        seo={},
    )
    async_session.add(home_page)
    await async_session.flush()

    editor = EditorService(async_session)

    # 2. Attempt to add a page to template-origin site -> must raise template_page_creation_denied
    add_page_op = AddPage(name="About", slug="about")
    with pytest.raises(ApiProblem) as exc_info:
        await editor.apply(website.id, sample_user.id, [add_page_op])

    assert exc_info.value.status_code == 409
    assert exc_info.value.title == "template_page_creation_denied"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ai_site_origin_page_expansion(async_session, sample_user, sample_template_version):
    # 1. Create an AI-origin website
    website = Website(
        owner_user_id=sample_user.id,
        source_template_version_id=sample_template_version.id,
        site_origin="AI",
        display_name="AI Site",
        status="DRAFT",
        theme={"color": "emerald"},
    )
    async_session.add(website)
    await async_session.flush()

    home_page = WebsitePage(
        website_id=website.id,
        source_template_page_id="p1",
        name="Home",
        slug="",
        is_home=True,
        show_in_navigation=True,
        status="DRAFT",
        content={"components": []},
        seo={},
    )
    async_session.add(home_page)
    await async_session.flush()

    editor = EditorService(async_session)

    # 2. Add page to AI-origin site -> succeeds
    add_page_op = AddPage(name="Services", slug="services")
    mutation = await editor.apply(website.id, sample_user.id, [add_page_op])
    assert mutation.website.site_origin == "AI"

    website_service = WebsiteService(async_session)
    pages = await website_service.pages(website.id)
    assert len(pages) == 2
    assert any(p.slug == "services" for p in pages)
