from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.template_models import Template, TemplateVersion
from zylora_api.db.website_models import (
    Website,
    WebsiteOwnership,
    WebsitePage,
    WebsitePagePathChange,
)
from zylora_api.modules.templates.service import problem
from zylora_api.modules.websites.schemas import PageCreateRequest, PageUpdateRequest

MAX_PAGE_DEPTH = 12
MAX_WEBSITE_PAGES = 500
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_ROOT_SLUGS = frozenset(
    {
        "_next",
        "admin",
        "api",
        "app",
        "forgot-password",
        "health",
        "login",
        "reset-password",
        "signup",
        "templates",
        "verify-email",
    }
)


@dataclass(frozen=True)
class PathChange:
    page_id: UUID
    old_path: str
    new_path: str


@dataclass(frozen=True)
class PageMutationResult:
    website: Website
    path_changes: list[PathChange]


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


def validate_page_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise problem(422, "invalid_page_name", "Page name cannot be empty.")
    return normalized


def validate_page_slug(slug: str, parent_page_id: UUID | None) -> str:
    if slug != slug.strip() or not SLUG_PATTERN.fullmatch(slug):
        raise problem(
            422,
            "invalid_page_slug",
            "Use lowercase letters, numbers, and single hyphens in the URL slug.",
        )
    if parent_page_id is None and slug in RESERVED_ROOT_SLUGS:
        raise problem(
            409,
            "reserved_page_slug",
            "That root URL is reserved by the Zylora platform.",
        )
    return slug


def validate_page_seo(seo: dict[str, str]) -> dict[str, str]:
    unsupported = set(seo) - {"title", "description"}
    if unsupported:
        raise problem(
            422,
            "unsupported_page_seo_setting",
            "Only the basic SEO title and description are available in this phase.",
        )
    title = seo.get("title", "").strip()
    description = seo.get("description", "").strip()
    if len(title) > 70 or len(description) > 180:
        raise problem(
            422,
            "invalid_page_seo",
            "SEO titles must be at most 70 characters and descriptions at most 180.",
        )
    return {"title": title, "description": description}


def page_paths(pages: list[WebsitePage]) -> dict[UUID, str]:
    page_map = {page.id: page for page in pages}
    return {page.id: resolve_page_path(page, page_map) for page in pages}


def build_navigation(pages: list[WebsitePage]) -> list[dict[str, object]]:
    page_map = {page.id: page for page in pages}
    visible_ids = {
        page.id for page in pages if page.show_in_navigation and page.status != "ARCHIVED"
    }
    grouped: dict[UUID | None, list[WebsitePage]] = {}
    for page in pages:
        if page.id not in visible_ids:
            continue
        parent_id = page.parent_page_id
        seen = {page.id}
        while parent_id is not None and parent_id not in visible_ids:
            if parent_id in seen:
                raise problem(409, "page_hierarchy_cycle", "The page hierarchy contains a cycle.")
            seen.add(parent_id)
            parent = page_map.get(parent_id)
            parent_id = parent.parent_page_id if parent else None
        grouped.setdefault(parent_id, []).append(page)
    paths = page_paths(pages)

    def nodes(parent_id: UUID | None, branch: set[UUID]) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for page in sorted(
            grouped.get(parent_id, []),
            key=lambda item: (0 if item.is_home else 1, item.sort_order, str(item.id)),
        ):
            if page.id in branch:
                raise problem(409, "page_hierarchy_cycle", "The page hierarchy contains a cycle.")
            result.append(
                {
                    "page_id": page.id,
                    "label": page.name,
                    "path": paths[page.id],
                    "children": nodes(page.id, branch | {page.id}),
                }
            )
        return result

    return nodes(None, set())


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
            theme=deepcopy(version.document["theme"]),
        )
        self.session.add(website)
        await self.session.flush()
        self.session.add(
            WebsiteOwnership(
                website_id=website.id,
                owner_user_id=owner_user_id,
                acquisition_reason="TEMPLATE_CREATION",
            )
        )
        template_pages = list(version.document.get("pages", []))
        id_map = {str(page["id"]): uuid4() for page in template_pages}
        source_pages: dict[str, dict[str, object]] = {
            str(item["id"]): item for item in template_pages
        }

        def hierarchy_sort_key(item: dict[str, object]) -> tuple[int, int, str]:
            depth = 0
            parent_id = item.get("parent_page_id")
            seen: set[str] = set()
            while parent_id is not None:
                parent_key = str(parent_id)
                if parent_key in seen or parent_key not in source_pages:
                    break
                seen.add(parent_key)
                depth += 1
                parent_id = source_pages[parent_key].get("parent_page_id")
            return depth, int(str(item.get("sort_order", 0))), str(item["id"])

        current_depth = -1
        for page in sorted(template_pages, key=hierarchy_sort_key):
            page_depth = hierarchy_sort_key(page)[0]
            if current_depth >= 0 and page_depth != current_depth:
                await self.session.flush()
            current_depth = page_depth
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
        from zylora_api.modules.editor.revisions import RevisionService

        pages = await self.pages(website.id)
        await RevisionService(self.session).capture(
            website,
            pages,
            source="TEMPLATE",
            actor_user_id=owner_user_id,
            summary=f"Created from {template.name}",
        )
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

    async def _editable_state(
        self, website_id: UUID, owner_user_id: UUID
    ) -> tuple[Website, list[WebsitePage]]:
        website = await self.session.scalar(
            select(Website)
            .where(Website.id == website_id, Website.owner_user_id == owner_user_id)
            .with_for_update()
        )
        if not website:
            raise problem(404, "website_not_found", "Website not found.")
        if website.status != "DRAFT":
            raise problem(
                409,
                "website_not_editable",
                "Only Draft Websites can be changed in the Page Manager.",
            )
        pages = list(
            (
                await self.session.scalars(
                    select(WebsitePage)
                    .where(WebsitePage.website_id == website.id)
                    .order_by(WebsitePage.sort_order, WebsitePage.id)
                    .with_for_update()
                )
            ).all()
        )
        return website, pages

    @staticmethod
    def _parent(
        pages: list[WebsitePage], page: WebsitePage, parent_page_id: UUID | None
    ) -> WebsitePage | None:
        if parent_page_id is None:
            return None
        parent = next((item for item in pages if item.id == parent_page_id), None)
        if not parent:
            raise problem(
                409, "cross_website_parent", "A page parent must belong to the same Website."
            )
        if parent.id == page.id:
            raise problem(409, "page_self_parent", "A page cannot be its own parent.")
        if parent.is_home:
            raise problem(
                409,
                "home_page_cannot_be_parent",
                "The home page cannot be used as a nested URL parent.",
            )
        return parent

    @staticmethod
    def _ensure_slug_available(page: WebsitePage, pages: list[WebsitePage]) -> None:
        conflict = next(
            (
                item
                for item in pages
                if item.id != page.id
                and item.parent_page_id == page.parent_page_id
                and item.slug == page.slug
            ),
            None,
        )
        if conflict:
            raise problem(
                409,
                "duplicate_page_slug",
                "Another page at this level already uses that URL slug.",
            )

    @staticmethod
    def _place(
        pages: list[WebsitePage],
        page: WebsitePage,
        old_parent_page_id: UUID | None,
        position: int,
    ) -> None:
        for parent_id in {old_parent_page_id, page.parent_page_id}:
            siblings = sorted(
                (item for item in pages if item.parent_page_id == parent_id and item.id != page.id),
                key=lambda item: (0 if item.is_home else 1, item.sort_order, str(item.id)),
            )
            if parent_id == page.parent_page_id:
                insert_at = min(position, len(siblings))
                if not page.is_home and siblings and siblings[0].is_home:
                    insert_at = max(1, insert_at)
                siblings.insert(insert_at, page)
            for index, sibling in enumerate(siblings):
                sibling.sort_order = index

    def _record_path_changes(
        self,
        website: Website,
        actor_user_id: UUID,
        before: dict[UUID, str],
        after: dict[UUID, str],
        reason: str,
    ) -> list[PathChange]:
        changes: list[PathChange] = []
        for page_id in sorted(before.keys() & after.keys(), key=str):
            if before[page_id] == after[page_id]:
                continue
            change = PathChange(
                page_id=page_id,
                old_path=before[page_id],
                new_path=after[page_id],
            )
            changes.append(change)
            self.session.add(
                WebsitePagePathChange(
                    website_id=website.id,
                    page_id=page_id,
                    actor_user_id=actor_user_id,
                    old_path=change.old_path,
                    new_path=change.new_path,
                    reason=reason,
                )
            )
        return changes

    async def add_page(
        self, website_id: UUID, owner_user_id: UUID, payload: PageCreateRequest
    ) -> PageMutationResult:
        website, pages = await self._editable_state(website_id, owner_user_id)
        if len(pages) >= MAX_WEBSITE_PAGES:
            raise problem(
                409,
                "website_page_capacity_reached",
                "This Website has reached the 500-page technical safety limit.",
            )
        page_id = uuid4()
        page = WebsitePage(
            id=page_id,
            website_id=website.id,
            source_template_page_id=f"user:{page_id.hex}",
            parent_page_id=payload.parent_page_id,
            name=validate_page_name(payload.name),
            slug=validate_page_slug(payload.slug, payload.parent_page_id),
            sort_order=payload.sort_order,
            is_home=False,
            show_in_navigation=payload.show_in_navigation,
            status=payload.status,
            content={
                "components": [
                    {
                        "id": f"hero-{page_id.hex[:20]}",
                        "type": "HERO",
                        "props": {
                            "heading": validate_page_name(payload.name),
                            "body": "Add your page content.",
                        },
                        "children": [],
                        "responsive": {},
                        "interactions": [],
                    }
                ]
            },
            seo=validate_page_seo(payload.seo),
        )
        self._parent(pages, page, page.parent_page_id)
        pages.append(page)
        self._ensure_slug_available(page, pages)
        resolve_page_path(page, {item.id: item for item in pages})
        self._place(pages, page, page.parent_page_id, payload.sort_order)
        website.updated_at = datetime.now(UTC)
        self.session.add(page)
        await self.session.flush()
        from zylora_api.modules.editor.revisions import RevisionService

        await RevisionService(self.session).capture(
            website,
            pages,
            source="MANUAL",
            actor_user_id=owner_user_id,
            summary=f"Added page {page.name}",
            operation_id=uuid4(),
        )
        return PageMutationResult(website=website, path_changes=[])

    async def update_page(
        self,
        website_id: UUID,
        page_id: UUID,
        owner_user_id: UUID,
        payload: PageUpdateRequest,
    ) -> PageMutationResult:
        website, pages = await self._editable_state(website_id, owner_user_id)
        page = next((item for item in pages if item.id == page_id), None)
        if not page:
            raise problem(404, "page_not_found", "Page not found.")
        fields = payload.model_fields_set
        old_parent_page_id = page.parent_page_id
        before = page_paths(pages)
        target_parent_id = (
            payload.parent_page_id if "parent_page_id" in fields else page.parent_page_id
        )
        if page.is_home and target_parent_id is not None:
            raise problem(409, "home_page_cannot_be_nested", "The home page must remain at root.")
        self._parent(pages, page, target_parent_id)
        target_slug = payload.slug if "slug" in fields else page.slug
        if page.is_home and "slug" in fields:
            raise problem(409, "home_page_slug_locked", "The home page always resolves to '/'.")
        if not page.is_home:
            page.slug = validate_page_slug(target_slug or "", target_parent_id)
        if "name" in fields:
            page.name = validate_page_name(payload.name or "")
        if "show_in_navigation" in fields:
            page.show_in_navigation = bool(payload.show_in_navigation)
        if "status" in fields:
            if page.is_home and payload.status != "DRAFT":
                raise problem(
                    409,
                    "home_page_status_locked",
                    "The home page must remain an active Draft page.",
                )
            page.status = payload.status or page.status
        if "seo" in fields:
            page.seo = validate_page_seo(payload.seo or {})
        page.parent_page_id = target_parent_id
        self._ensure_slug_available(page, pages)
        resolve_page_path(page, {item.id: item for item in pages})
        if "parent_page_id" in fields or "sort_order" in fields:
            position = (
                payload.sort_order
                if payload.sort_order is not None
                else len([item for item in pages if item.parent_page_id == target_parent_id])
            )
            self._place(pages, page, old_parent_page_id, position)
        after = page_paths(pages)
        changes = self._record_path_changes(website, owner_user_id, before, after, "PAGE_SETTINGS")
        website.updated_at = datetime.now(UTC)
        await self.session.flush()
        from zylora_api.modules.editor.revisions import RevisionService

        await RevisionService(self.session).capture(
            website,
            pages,
            source="MANUAL",
            actor_user_id=owner_user_id,
            summary=f"Updated page {page.name}",
            operation_id=uuid4(),
        )
        return PageMutationResult(website=website, path_changes=changes)

    async def delete_page(
        self, website_id: UUID, page_id: UUID, owner_user_id: UUID
    ) -> PageMutationResult:
        website, pages = await self._editable_state(website_id, owner_user_id)
        page = next((item for item in pages if item.id == page_id), None)
        if not page:
            raise problem(404, "page_not_found", "Page not found.")
        if page.is_home:
            raise problem(
                409,
                "home_page_delete_forbidden",
                "Assign another home page before deleting the current home page.",
            )
        before = page_paths(pages)
        children = sorted(
            (item for item in pages if item.parent_page_id == page.id),
            key=lambda item: (item.sort_order, str(item.id)),
        )
        target_parent_id = page.parent_page_id
        occupied = {
            item.slug
            for item in pages
            if item.id != page.id
            and item not in children
            and item.parent_page_id == target_parent_id
        }
        promoted_slugs: set[str] = set()
        for child in children:
            validate_page_slug(child.slug, target_parent_id)
            if child.slug in occupied or child.slug in promoted_slugs:
                raise problem(
                    409,
                    "delete_parent_slug_conflict",
                    "A child cannot be promoted because its URL slug conflicts at the new level.",
                )
            promoted_slugs.add(child.slug)
        base_order = 1 + max(
            (
                item.sort_order
                for item in pages
                if item.id != page.id
                and item not in children
                and item.parent_page_id == target_parent_id
            ),
            default=-1,
        )
        for offset, child in enumerate(children):
            child.parent_page_id = target_parent_id
            child.sort_order = base_order + offset
        remaining = [item for item in pages if item.id != page.id]
        for parent_id in {page.id, target_parent_id}:
            siblings = sorted(
                (item for item in remaining if item.parent_page_id == parent_id),
                key=lambda item: (0 if item.is_home else 1, item.sort_order, str(item.id)),
            )
            for index, sibling in enumerate(siblings):
                sibling.sort_order = index
        after = page_paths(remaining)
        changes = self._record_path_changes(
            website, owner_user_id, before, after, "DELETE_PROMOTE_CHILDREN"
        )
        await self.session.delete(page)
        website.updated_at = datetime.now(UTC)
        await self.session.flush()
        from zylora_api.modules.editor.revisions import RevisionService

        await RevisionService(self.session).capture(
            website,
            remaining,
            source="MANUAL",
            actor_user_id=owner_user_id,
            summary=f"Deleted page {page.name}; promoted its children",
            operation_id=uuid4(),
        )
        return PageMutationResult(website=website, path_changes=changes)
