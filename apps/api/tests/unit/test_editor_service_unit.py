from __future__ import annotations

from uuid import uuid4

import pytest
from zylora_api.db.website_models import Website, WebsitePage
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.editor.schemas import (
    EditPlan,
    InsertComponent,
    MoveComponent,
    RemoveComponent,
    SetComponentProp,
    SetNavigationVisibility,
    SetPageSeo,
    SetThemeToken,
)
from zylora_api.modules.editor.service import (
    EditorService,
    _component_props,
    _new_component,
    _walk_components,
    ai_plan_cost,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)


def page() -> WebsitePage:
    return WebsitePage(
        id=uuid4(),
        website_id=uuid4(),
        source_template_page_id="home",
        parent_page_id=None,
        name="Home",
        slug="",
        sort_order=0,
        is_home=True,
        show_in_navigation=True,
        status="DRAFT",
        content={
            "components": [
                {
                    "id": "hero-home",
                    "type": "HERO",
                    "props": {"heading": "Home", "body": "Welcome."},
                    "children": [],
                    "responsive": {},
                    "interactions": [],
                },
                {
                    "id": "copy-home",
                    "type": "RICH_TEXT",
                    "props": {"text": "Copy"},
                    "children": [],
                    "responsive": {},
                    "interactions": [],
                },
            ]
        },
        seo={"title": "Home", "description": "Welcome home."},
    )


def insert(kind: str) -> InsertComponent:
    return InsertComponent(
        kind="INSERT_COMPONENT",
        page_id=uuid4(),
        component_type=kind,
        position=1,
        heading="Heading",
        body="Body",
        items=["One"],
    )  # type: ignore[arg-type]


def test_component_builders_and_cost_weights_cover_supported_vocabulary() -> None:
    assert _component_props(insert("SECTION"))["tone"] == "surface"
    assert _component_props(insert("HEADING")) == {"text": "Heading", "level": 2}
    assert _component_props(insert("RICH_TEXT")) == {"text": "Body"}
    assert _component_props(insert("FAQ"))["items"] == ["One"]
    assert _component_props(insert("TESTIMONIALS"))["heading"] == "Heading"
    component = _new_component(insert("SECTION"))
    assert component["type"] == "SECTION" and str(component["id"]).startswith("ai-")
    nested = [{"id": "parent", "children": [{"id": "child", "children": "invalid"}]}]
    assert [item["id"] for item in _walk_components(nested)] == ["parent", "child"]

    plan = EditPlan(
        summary="Large transformation",
        operations=[insert("SECTION"), insert("SECTION"), insert("SECTION")],
    )
    assert ai_plan_cost(plan) == 15


def test_component_invariants_reject_unsafe_changes_and_support_reorder_remove() -> None:
    service = EditorService(FakeSession())  # type: ignore[arg-type]
    model = page()
    with pytest.raises(AuthProblem, match="Page not found"):
        service._page([], uuid4())
    invalid_content = page()
    invalid_content.content = {"components": "invalid"}
    with pytest.raises(AuthProblem) as invalid:
        service._component(invalid_content, "hero-home")
    assert invalid.value.code == "page_content_invalid"
    with pytest.raises(AuthProblem) as missing:
        service._component(model, "missing")
    assert missing.value.code == "component_not_found"

    with pytest.raises(AuthProblem) as unsupported:
        service._set_component_prop(
            model,
            SetComponentProp(
                kind="SET_COMPONENT_PROP",
                page_id=model.id,
                component_id="hero-home",
                property="onclick",
                value="unsafe",
            ),
        )
    assert unsupported.value.code == "unsupported_component_property"

    with pytest.raises(AuthProblem) as h1:
        service._remove_component(
            model,
            RemoveComponent(kind="REMOVE_COMPONENT", page_id=model.id, component_id="hero-home"),
        )
    assert h1.value.code == "page_h1_required"
    with pytest.raises(AuthProblem) as remove_missing:
        service._remove_component(
            model,
            RemoveComponent(kind="REMOVE_COMPONENT", page_id=model.id, component_id="missing"),
        )
    assert remove_missing.value.code == "component_not_found"

    service._move_component(
        model,
        MoveComponent(
            kind="MOVE_COMPONENT", page_id=model.id, component_id="copy-home", position=0
        ),
    )
    assert model.content["components"][0]["id"] == "copy-home"
    with pytest.raises(AuthProblem) as move_missing:
        service._move_component(
            model,
            MoveComponent(
                kind="MOVE_COMPONENT", page_id=model.id, component_id="missing", position=0
            ),
        )
    assert move_missing.value.code == "component_not_found"
    service._remove_component(
        model,
        RemoveComponent(kind="REMOVE_COMPONENT", page_id=model.id, component_id="copy-home"),
    )
    assert len(model.content["components"]) == 1

    capacity = page()
    capacity.content = {"components": [{"id": str(index)} for index in range(80)]}
    with pytest.raises(AuthProblem) as full:
        service._insert_component(capacity, insert("SECTION"))
    assert full.value.code == "page_component_capacity"


def test_operation_dispatch_updates_theme_seo_navigation_and_content() -> None:
    service = EditorService(FakeSession())  # type: ignore[arg-type]
    model = page()
    site = Website(
        id=model.website_id,
        owner_user_id=uuid4(),
        source_template_version_id=uuid4(),
        display_name="Draft",
        status="DRAFT",
        theme={"primary": "#000000"},
        revision=1,
    )
    service._apply_operation(
        site,
        [model],
        SetThemeToken(kind="SET_THEME_TOKEN", property="primary", value="#FFFFFF"),
        site.owner_user_id,
    )
    service._apply_operation(
        site,
        [model],
        SetPageSeo(
            kind="SET_PAGE_SEO",
            page_id=model.id,
            title="New title",
            description="New description",
        ),
        site.owner_user_id,
    )
    service._apply_operation(
        site,
        [model],
        SetNavigationVisibility(
            kind="SET_NAVIGATION_VISIBILITY",
            page_id=model.id,
            show_in_navigation=False,
        ),
        site.owner_user_id,
    )
    service._apply_operation(
        site,
        [model],
        insert("SECTION").model_copy(update={"page_id": model.id}),
        site.owner_user_id,
    )
    assert site.theme["primary"] == "#FFFFFF"
    assert model.seo["title"] == "New title"
    assert model.show_in_navigation is False
    assert len(model.content["components"]) == 3

    class Unknown:
        kind = "UNKNOWN"

    with pytest.raises(AuthProblem) as unknown:
        service._apply_operation(site, [model], Unknown(), site.owner_user_id)  # type: ignore[arg-type]
    assert unknown.value.code == "unsupported_editor_operation"
