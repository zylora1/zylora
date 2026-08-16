from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.website_models import AiOperation, Website, WebsitePage, WebsiteVersion
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.editor.provider import (
    PROMPT_TEMPLATE_VERSION,
    AiPlanner,
    AiPlanningError,
    PlanningContext,
)
from zylora_api.modules.editor.revisions import AiCreditService, RevisionService
from zylora_api.modules.editor.schemas import (
    AddPage,
    AiEditRequest,
    EditorOperation,
    EditPlan,
    InsertComponent,
    ManualEditRequest,
    MoveComponent,
    MovePage,
    RemoveComponent,
    SetComponentProp,
    SetNavigationVisibility,
    SetPageSeo,
    SetThemeToken,
)
from zylora_api.modules.templates.document import COMPONENT_REGISTRY
from zylora_api.modules.templates.service import problem
from zylora_api.modules.websites.service import (
    MAX_WEBSITE_PAGES,
    WebsiteService,
    page_paths,
    resolve_page_path,
    validate_page_name,
    validate_page_seo,
    validate_page_slug,
)


@dataclass(frozen=True)
class AppliedEdit:
    website: Website
    version: WebsiteVersion
    credits_used: int


AI_OPERATION_COSTS = {
    "SET_COMPONENT_PROP": 1,
    "SET_THEME_TOKEN": 1,
    "INSERT_COMPONENT": 5,
    "REMOVE_COMPONENT": 1,
    "MOVE_COMPONENT": 1,
    "SET_PAGE_SEO": 1,
    "ADD_PAGE": 8,
    "MOVE_PAGE": 2,
    "SET_NAVIGATION_VISIBILITY": 1,
}


def ai_plan_cost(plan: EditPlan) -> int:
    return min(15, max(1, sum(AI_OPERATION_COSTS[item.kind] for item in plan.operations)))


def _component_props(operation: InsertComponent) -> dict[str, Any]:
    if operation.component_type == "SECTION":
        return {"heading": operation.heading, "body": operation.body, "tone": "surface"}
    if operation.component_type == "HEADING":
        return {"text": operation.heading or operation.body, "level": 2}
    if operation.component_type == "RICH_TEXT":
        return {"text": operation.body or operation.heading}
    if operation.component_type in {"TESTIMONIALS", "FAQ"}:
        return {"heading": operation.heading, "items": operation.items}
    raise problem(422, "unsupported_component", "That component is not editor-compatible.")


def _new_component(operation: InsertComponent) -> dict[str, Any]:
    return {
        "id": f"ai-{uuid4().hex[:20]}",
        "type": operation.component_type,
        "props": _component_props(operation),
        "children": [],
        "responsive": {},
        "interactions": [],
    }


def _walk_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for component in components:
        found.append(component)
        children = component.get("children", [])
        if isinstance(children, list):
            found.extend(_walk_components([item for item in children if isinstance(item, dict)]))
    return found


class EditorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.websites = WebsiteService(session)
        self.revisions = RevisionService(session)
        self.credits = AiCreditService(session)

    async def _website_and_pages(
        self, website_id: UUID, owner_user_id: UUID
    ) -> tuple[Website, list[WebsitePage]]:
        return await self.websites._editable_state(website_id, owner_user_id)

    async def _idempotent_version(
        self, website_id: UUID, operation_id: UUID
    ) -> WebsiteVersion | None:
        version: WebsiteVersion | None = await self.session.scalar(
            select(WebsiteVersion).where(
                WebsiteVersion.website_id == website_id,
                WebsiteVersion.operation_id == operation_id,
            )
        )
        return version

    @staticmethod
    def _page(pages: list[WebsitePage], page_id: UUID) -> WebsitePage:
        page = next((item for item in pages if item.id == page_id), None)
        if not page:
            raise problem(404, "page_not_found", "Page not found in this Website.")
        return page

    @staticmethod
    def _assert_scope(
        operations: list[EditorOperation], scope: str, selected_page_id: UUID | None
    ) -> None:
        if scope != "PAGE":
            return
        for operation in operations:
            page_id = getattr(operation, "page_id", None)
            if (
                isinstance(operation, (AddPage, MovePage, SetThemeToken))
                or page_id != selected_page_id
            ):
                raise problem(
                    422,
                    "ai_scope_violation",
                    "The proposed change exceeds the selected page. Nothing was changed.",
                )

    @staticmethod
    def _component(page: WebsitePage, component_id: str) -> dict[str, Any]:
        components = page.content.get("components", [])
        if not isinstance(components, list):
            raise problem(409, "page_content_invalid", "This page cannot be edited safely.")
        match = next(
            (item for item in _walk_components(components) if item.get("id") == component_id),
            None,
        )
        if not match:
            raise problem(404, "component_not_found", "The selected component no longer exists.")
        return match

    def _set_component_prop(self, page: WebsitePage, operation: SetComponentProp) -> None:
        page.content = deepcopy(page.content)
        component = self._component(page, operation.component_id)
        registry = COMPONENT_REGISTRY.get(str(component.get("type", "")))
        if not registry or operation.property not in registry.allowed_props:
            raise problem(
                422,
                "unsupported_component_property",
                "That component property cannot be changed.",
            )
        props = deepcopy(component.get("props", {}))
        props[operation.property] = operation.value
        component["props"] = props

    def _insert_component(self, page: WebsitePage, operation: InsertComponent) -> None:
        components = deepcopy(page.content.get("components", []))
        if len(components) >= 80:
            raise problem(409, "page_component_capacity", "This page is at its component limit.")
        components.insert(min(operation.position, len(components)), _new_component(operation))
        page.content = {**page.content, "components": components}

    def _remove_component(self, page: WebsitePage, operation: RemoveComponent) -> None:
        components = deepcopy(page.content.get("components", []))
        index = next(
            (
                position
                for position, item in enumerate(components)
                if item.get("id") == operation.component_id
            ),
            None,
        )
        if index is None:
            raise problem(404, "component_not_found", "The selected component no longer exists.")
        if (
            components[index].get("type") in {"HERO", "HEADING"}
            and sum(
                item.get("type") in {"HERO", "HEADING"}
                and (item.get("type") == "HERO" or item.get("props", {}).get("level") == 1)
                for item in components
            )
            == 1
        ):
            raise problem(
                409, "page_h1_required", "Every page must retain exactly one main heading."
            )
        components.pop(index)
        page.content = {**page.content, "components": components}

    def _move_component(self, page: WebsitePage, operation: MoveComponent) -> None:
        components = deepcopy(page.content.get("components", []))
        index = next(
            (
                position
                for position, item in enumerate(components)
                if item.get("id") == operation.component_id
            ),
            None,
        )
        if index is None:
            raise problem(404, "component_not_found", "The selected component no longer exists.")
        component = components.pop(index)
        components.insert(min(operation.position, len(components)), component)
        page.content = {**page.content, "components": components}

    def _add_page(self, website: Website, pages: list[WebsitePage], operation: AddPage) -> None:
        if getattr(website, "site_origin", "TEMPLATE") == "TEMPLATE":
            raise problem(
                409,
                "template_page_creation_denied",
                "Template-origin websites have a fixed page set. "
                "Additional pages cannot be created.",
            )
        if len(pages) >= MAX_WEBSITE_PAGES:
            raise problem(
                409, "website_page_capacity_reached", "This Website is at its safety limit."
            )
        page_id = uuid4()
        page = WebsitePage(
            id=page_id,
            website_id=website.id,
            source_template_page_id=f"editor:{page_id.hex}",
            parent_page_id=operation.parent_page_id,
            name=validate_page_name(operation.name),
            slug=validate_page_slug(operation.slug, operation.parent_page_id),
            sort_order=len(
                [item for item in pages if item.parent_page_id == operation.parent_page_id]
            ),
            is_home=False,
            show_in_navigation=operation.show_in_navigation,
            status="DRAFT",
            content={
                "components": [
                    {
                        "id": f"hero-{page_id.hex[:20]}",
                        "type": "HERO",
                        "props": {"heading": operation.heading, "body": operation.body},
                        "children": [],
                        "responsive": {},
                        "interactions": [],
                    },
                    *(
                        [
                            {
                                "id": f"faq-{page_id.hex[:20]}",
                                "type": "FAQ",
                                "props": {
                                    "heading": "Frequently asked questions",
                                    "items": operation.items,
                                },
                                "children": [],
                                "responsive": {},
                                "interactions": [],
                            }
                        ]
                        if operation.section_type == "FAQ"
                        else []
                    ),
                ]
            },
            seo={"title": operation.name[:60], "description": operation.body[:160]},
        )
        self.websites._parent(pages, page, page.parent_page_id)
        pages.append(page)
        self.websites._ensure_slug_available(page, pages)
        resolve_page_path(page, {item.id: item for item in pages})
        self.session.add(page)

    def _move_page(
        self, website: Website, pages: list[WebsitePage], operation: MovePage, actor_user_id: UUID
    ) -> None:
        page = self._page(pages, operation.page_id)
        if page.is_home and operation.parent_page_id is not None:
            raise problem(409, "home_page_cannot_be_nested", "The home page must remain at root.")
        before = page_paths(pages)
        old_parent = page.parent_page_id
        self.websites._parent(pages, page, operation.parent_page_id)
        page.parent_page_id = operation.parent_page_id
        if not page.is_home:
            validate_page_slug(page.slug, page.parent_page_id)
        self.websites._ensure_slug_available(page, pages)
        resolve_page_path(page, {item.id: item for item in pages})
        self.websites._place(pages, page, old_parent, operation.position)
        self.websites._record_path_changes(
            website, actor_user_id, before, page_paths(pages), "AI_OR_MANUAL_EDIT"
        )

    def _apply_operation(
        self,
        website: Website,
        pages: list[WebsitePage],
        operation: EditorOperation,
        actor_user_id: UUID,
    ) -> None:
        if isinstance(operation, SetComponentProp):
            page = self._page(pages, operation.page_id)
            self._set_component_prop(page, operation)
        elif isinstance(operation, SetThemeToken):
            website.theme = {**website.theme, operation.property: operation.value}
        elif isinstance(operation, InsertComponent):
            self._insert_component(self._page(pages, operation.page_id), operation)
        elif isinstance(operation, RemoveComponent):
            self._remove_component(self._page(pages, operation.page_id), operation)
        elif isinstance(operation, MoveComponent):
            self._move_component(self._page(pages, operation.page_id), operation)
        elif isinstance(operation, SetPageSeo):
            page = self._page(pages, operation.page_id)
            page.seo = validate_page_seo(
                {"title": operation.title, "description": operation.description}
            )
        elif isinstance(operation, AddPage):
            self._add_page(website, pages, operation)
        elif isinstance(operation, MovePage):
            self._move_page(website, pages, operation, actor_user_id)
        elif isinstance(operation, SetNavigationVisibility):
            page = self._page(pages, operation.page_id)
            page.show_in_navigation = operation.show_in_navigation
        else:
            raise problem(422, "unsupported_editor_operation", "That edit is not supported.")

    async def apply_plan(
        self,
        *,
        website_id: UUID,
        owner_user_id: UUID,
        operation_id: UUID,
        base_revision: int,
        plan: EditPlan,
        scope: str,
        selected_page_id: UUID | None,
        source: str,
        ai_operation_id: UUID | None = None,
        cost: int = 0,
    ) -> AppliedEdit:
        existing = await self._idempotent_version(website_id, operation_id)
        if existing:
            website = await self.websites.get_for_owner(website_id, owner_user_id)
            return AppliedEdit(website, existing, 0)
        self._assert_scope(plan.operations, scope, selected_page_id)
        website, pages = await self._website_and_pages(website_id, owner_user_id)
        if website.revision != base_revision:
            raise problem(
                409,
                "website_revision_conflict",
                "This Draft changed elsewhere. Refresh before applying this edit.",
            )
        for operation in plan.operations:
            self._apply_operation(website, pages, operation, owner_user_id)
        website.updated_at = datetime.now(UTC)
        await self.session.flush()
        if source == "AI":
            await self.credits.debit(owner_user_id, operation_id, cost)
        version = await self.revisions.capture(
            website,
            pages,
            source=source,
            actor_user_id=owner_user_id,
            summary=plan.summary,
            operation_id=operation_id,
            ai_operation_id=ai_operation_id,
        )
        return AppliedEdit(website, version, cost if source == "AI" else 0)

    async def manual_edit(
        self, website_id: UUID, owner_user_id: UUID, request: ManualEditRequest
    ) -> AppliedEdit:
        return await self.apply_plan(
            website_id=website_id,
            owner_user_id=owner_user_id,
            operation_id=request.operation_id,
            base_revision=request.base_revision,
            plan=EditPlan(summary=request.summary, operations=request.operations),
            scope=request.scope,
            selected_page_id=request.selected_page_id,
            source="MANUAL",
        )

    async def ai_edit(
        self,
        website_id: UUID,
        owner_user_id: UUID,
        request: AiEditRequest,
        planner: AiPlanner,
        safety_identifier: str,
    ) -> AppliedEdit:
        existing_operation = await self.session.get(AiOperation, request.operation_id)
        if existing_operation:
            if (
                existing_operation.user_id != owner_user_id
                or existing_operation.website_id != website_id
            ):
                raise problem(409, "ai_operation_conflict", "That operation ID is already in use.")
            if existing_operation.status == "SUCCEEDED":
                version = await self.session.scalar(
                    select(WebsiteVersion).where(
                        WebsiteVersion.ai_operation_id == existing_operation.id
                    )
                )
                if version:
                    website = await self.websites.get_for_owner(website_id, owner_user_id)
                    return AppliedEdit(website, version, existing_operation.cost_credits)
            raise problem(409, "ai_operation_not_retryable", "Use a new operation ID to retry.")

        website = await self.websites.get_for_owner(website_id, owner_user_id)
        if website.revision != request.base_revision:
            raise problem(409, "website_revision_conflict", "Refresh this Draft before using AI.")
        current = await self.revisions.current(website)
        pages = await self.websites.pages(website.id)
        document = deepcopy(current.document)
        by_document_id = {f"p{page.id.hex}": page for page in pages}
        for page in document.get("pages", []):
            if isinstance(page, dict) and page.get("id") in by_document_id:
                page["database_id"] = str(by_document_id[str(page["id"])].id)
        graph: list[dict[str, object]] = [
            {
                "id": str(page.id),
                "name": page.name,
                "path": page_paths(pages)[page.id],
                "parent_page_id": str(page.parent_page_id) if page.parent_page_id else None,
                "show_in_navigation": page.show_in_navigation,
            }
            for page in pages
        ]
        await self.session.commit()
        try:
            planned = await planner.plan(
                request,
                PlanningContext(document=document, page_graph=graph),
                safety_identifier,
            )
        except AiPlanningError as exc:
            await self._record_ai_failure(
                website_id, owner_user_id, request, exc.code, exc.safe_message
            )
            raise problem(503, exc.code, exc.safe_message) from exc

        cost = ai_plan_cost(planned.plan)
        ai_operation = AiOperation(
            id=request.operation_id,
            user_id=owner_user_id,
            website_id=website_id,
            status="PLANNING",
            scope=request.scope,
            selected_page_id=request.selected_page_id,
            prompt_digest=hashlib.sha256(request.prompt.encode()).hexdigest(),
            provider=planned.provider,
            model=planned.model,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
            base_revision=request.base_revision,
            cost_credits=cost,
            usage=planned.usage,
            latency_ms=planned.latency_ms,
            operation_summary=planned.plan.summary,
        )
        self.session.add(ai_operation)
        try:
            result = await self.apply_plan(
                website_id=website_id,
                owner_user_id=owner_user_id,
                operation_id=request.operation_id,
                base_revision=request.base_revision,
                plan=planned.plan,
                scope=request.scope,
                selected_page_id=request.selected_page_id,
                source="AI",
                ai_operation_id=ai_operation.id,
                cost=cost,
            )
            ai_operation.status = "SUCCEEDED"
            ai_operation.result_revision = result.version.revision
            ai_operation.completed_at = datetime.now(UTC)
            await self.session.flush()
            return result
        except Exception as exc:
            await self.session.rollback()
            code, message = self._safe_failure(exc)
            await self._record_ai_failure(
                website_id, owner_user_id, request, code, message, planned
            )
            raise

    @staticmethod
    def _safe_failure(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, AuthProblem):
            return exc.code, exc.detail
        return (
            "ai_apply_failed",
            "The AI change was not applied. Your Draft and credits were unchanged.",
        )

    async def _record_ai_failure(
        self,
        website_id: UUID,
        user_id: UUID,
        request: AiEditRequest,
        code: str,
        message: str,
        planned: Any | None = None,
    ) -> None:
        await self.session.rollback()
        self.session.add(
            AiOperation(
                id=request.operation_id,
                user_id=user_id,
                website_id=website_id,
                status="FAILED",
                scope=request.scope,
                selected_page_id=request.selected_page_id,
                prompt_digest=hashlib.sha256(request.prompt.encode()).hexdigest(),
                provider=getattr(planned, "provider", "UNAVAILABLE"),
                model=getattr(planned, "model", "UNAVAILABLE"),
                prompt_template_version=PROMPT_TEMPLATE_VERSION,
                base_revision=request.base_revision,
                cost_credits=0,
                usage=getattr(planned, "usage", {}),
                latency_ms=getattr(planned, "latency_ms", None),
                error_code=code,
                safe_error=message[:1000],
                completed_at=datetime.now(UTC),
            )
        )
        from zylora_api.modules.analytics.activation import ProductAnalyticsService

        await ProductAnalyticsService(self.session).record_event(
            event_type="AI_EDIT_FAILED",
            idempotency_key=f"ai-edit-failed:{request.operation_id}",
            user_id=user_id,
            website_id=website_id,
            properties={"error_code": code},
        )
        await self.session.commit()

    async def restore(
        self,
        website_id: UUID,
        owner_user_id: UUID,
        target_version_id: UUID,
        operation_id: UUID,
        base_revision: int,
    ) -> AppliedEdit:
        existing = await self._idempotent_version(website_id, operation_id)
        if existing:
            website = await self.websites.get_for_owner(website_id, owner_user_id)
            return AppliedEdit(website, existing, 0)
        website, _pages = await self._website_and_pages(website_id, owner_user_id)
        if website.revision != base_revision:
            raise problem(409, "website_revision_conflict", "Refresh before restoring a revision.")
        target = await self.session.get(WebsiteVersion, target_version_id)
        if not target or target.website_id != website.id:
            raise problem(404, "website_version_not_found", "Website revision not found.")
        await self.session.execute(
            delete(WebsitePage)
            .where(WebsitePage.website_id == website.id)
            .execution_options(synchronize_session=False)
        )
        for page in _pages:
            self.session.expunge(page)
        state = deepcopy(target.page_state)
        pending = {UUID(str(item["id"])): item for item in state}
        inserted: set[UUID] = set()
        while pending:
            progressed = False
            for page_id, item in list(pending.items()):
                parent_id = (
                    UUID(str(item["parent_page_id"])) if item.get("parent_page_id") else None
                )
                if parent_id is not None and parent_id not in inserted:
                    continue
                self.session.add(
                    WebsitePage(
                        id=page_id,
                        website_id=website.id,
                        source_template_page_id=str(item["source_template_page_id"]),
                        parent_page_id=parent_id,
                        name=str(item["name"]),
                        slug=str(item["slug"]),
                        sort_order=int(item["sort_order"]),
                        is_home=bool(item["is_home"]),
                        show_in_navigation=bool(item["show_in_navigation"]),
                        status=str(item["status"]),
                        content=deepcopy(item["content"]),
                        seo=deepcopy(item["seo"]),
                    )
                )
                inserted.add(page_id)
                del pending[page_id]
                progressed = True
            if not progressed:
                raise problem(409, "website_version_invalid", "The revision hierarchy is invalid.")
            await self.session.flush()
        website.theme = deepcopy(target.document["theme"])
        restored_pages = await self.websites.pages(website.id)
        version = await self.revisions.capture(
            website,
            restored_pages,
            source="RESTORE",
            actor_user_id=owner_user_id,
            summary=f"Restored revision {target.revision}",
            operation_id=operation_id,
            parent_version_id=website.current_version_id,
            document_override=target.document,
            page_state_override=state,
        )
        return AppliedEdit(website, version, 0)
