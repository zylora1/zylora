from __future__ import annotations

from copy import deepcopy
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.template_models import Template, TemplateVersion
from zylora_api.db.website_models import Website, WebsitePage
from zylora_api.modules.templates.service import problem

MAX_PAGE_DEPTH = 12


def resolve_page_path(page: WebsitePage, pages: dict[UUID, WebsitePage]) -> str:
    if page.is_home:
        return "/"
    segments: list[str] = []
    current: WebsitePage | None = page
    seen: set[UUID] = set()
    while current is not None:
        if current.id in seen:
            raise problem(409, "page_hierarchy_cycle", "The page hierarchy contains a cycle.")
        seen.add(current.id)
        if current.is_home:
            raise problem(
                409,
                "home_page_cannot_be_parent",
                "The home page cannot be used as a nested URL parent.",
            )
        segments.append(current.slug)
        current = pages.get(current.parent_page_id) if current.parent_page_id else None
        if len(segments) > MAX_PAGE_DEPTH:
            raise problem(
                409, "page_hierarchy_too_deep", "The page hierarchy exceeds the supported depth."
            )
    return "/" + "/".join(reversed(segments))


class WebsiteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def instantiate(self, template_slug: str, owner_user_id: UUID) -> Website:
        row = (
            await self.session.execute(
                select(Template, TemplateVersion)
                .join(TemplateVersion, Template.current_published_version_id == TemplateVersion.id)
                .where(
                    Template.slug == template_slug,
                    Template.status == "ACTIVE",
                    TemplateVersion.status == "PUBLISHED",
                )
            )
        ).one_or_none()
        if not row:
            raise problem(404, "template_not_found", "Published Template not found.")
        template, version = row
        website = Website(
            owner_user_id=owner_user_id,
            source_template_version_id=version.id,
            display_name=f"{template.name} Draft",
            status="DRAFT",
        )
        self.session.add(website)
        await self.session.flush()
        template_pages = list(version.document.get("pages", []))
        id_map = {str(page["id"]): uuid4() for page in template_pages}
        for page in sorted(template_pages, key=lambda item: int(item.get("sort_order", 0))):
            source_id = str(page["id"])
            parent_source = page.get("parent_page_id")
            is_home = bool(page.get("is_home", page.get("slug") == "home"))
            model = WebsitePage(
                id=id_map[source_id],
                website_id=website.id,
                source_template_page_id=source_id,
                parent_page_id=id_map.get(str(parent_source)) if parent_source else None,
                name=str(page["label"]),
                slug="" if is_home else str(page["slug"]),
                sort_order=int(page.get("sort_order", 0)),
                is_home=is_home,
                show_in_navigation=bool(page.get("show_in_navigation", True)),
                status="DRAFT",
                content={"components": deepcopy(page["components"])},
                seo=deepcopy(page["seo"]),
            )
            self.session.add(model)
        await self.session.flush()
        return website

    async def list_for_owner(self, owner_user_id: UUID) -> list[Website]:
        return list(
            (
                await self.session.scalars(
                    select(Website)
                    .where(Website.owner_user_id == owner_user_id)
                    .order_by(Website.updated_at.desc())
                )
            ).all()
        )

    async def get_for_owner(self, website_id: UUID, owner_user_id: UUID) -> Website:
        website = await self.session.scalar(
            select(Website).where(Website.id == website_id, Website.owner_user_id == owner_user_id)
        )
        if not website:
            raise problem(404, "website_not_found", "Website not found.")
        return website

    async def pages(self, website_id: UUID) -> list[WebsitePage]:
        return list(
            (
                await self.session.scalars(
                    select(WebsitePage)
                    .where(WebsitePage.website_id == website_id)
                    .order_by(WebsitePage.sort_order, WebsitePage.id)
                )
            ).all()
        )

    async def validate_parent(self, page: WebsitePage, parent_page_id: UUID | None) -> None:
        if parent_page_id is None:
            return
        parent = await self.session.get(WebsitePage, parent_page_id)
        if not parent or parent.website_id != page.website_id:
            raise problem(
                409, "cross_website_parent", "A page parent must belong to the same Website."
            )
        if parent.id == page.id:
            raise problem(409, "page_self_parent", "A page cannot be its own parent.")
        pages = {item.id: item for item in await self.pages(page.website_id)}
        pages[page.id] = page
        original = page.parent_page_id
        page.parent_page_id = parent.id
        try:
            resolve_page_path(page, pages)
        finally:
            page.parent_page_id = original
