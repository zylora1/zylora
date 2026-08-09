from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetComponentProp(Schema):
    kind: Literal["SET_COMPONENT_PROP"]
    page_id: UUID
    component_id: str = Field(min_length=1, max_length=64)
    property: str = Field(min_length=1, max_length=40)
    value: str | int | bool


class SetThemeToken(Schema):
    kind: Literal["SET_THEME_TOKEN"]
    property: Literal[
        "primary",
        "accent",
        "surface",
        "ink",
        "heading_font",
        "body_font",
    ]
    value: str = Field(min_length=1, max_length=80)


class InsertComponent(Schema):
    kind: Literal["INSERT_COMPONENT"]
    page_id: UUID
    component_type: Literal[
        "SECTION",
        "HEADING",
        "RICH_TEXT",
        "TESTIMONIALS",
        "FAQ",
    ]
    position: int = Field(default=0, ge=0, le=80)
    heading: str = Field(default="", max_length=160)
    body: str = Field(default="", max_length=2000)
    items: list[str] = Field(default_factory=list, max_length=12)


class RemoveComponent(Schema):
    kind: Literal["REMOVE_COMPONENT"]
    page_id: UUID
    component_id: str = Field(min_length=1, max_length=64)


class MoveComponent(Schema):
    kind: Literal["MOVE_COMPONENT"]
    page_id: UUID
    component_id: str = Field(min_length=1, max_length=64)
    position: int = Field(ge=0, le=80)


class SetPageSeo(Schema):
    kind: Literal["SET_PAGE_SEO"]
    page_id: UUID
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=160)


class AddPage(Schema):
    kind: Literal["ADD_PAGE"]
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=120)
    parent_page_id: UUID | None = None
    show_in_navigation: bool = True
    heading: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=2000)
    section_type: Literal["STANDARD", "FAQ"] = "STANDARD"
    items: list[str] = Field(default_factory=list, max_length=12)


class MovePage(Schema):
    kind: Literal["MOVE_PAGE"]
    page_id: UUID
    parent_page_id: UUID | None = None
    position: int = Field(default=0, ge=0, le=500)


class SetNavigationVisibility(Schema):
    kind: Literal["SET_NAVIGATION_VISIBILITY"]
    page_id: UUID
    show_in_navigation: bool


EditorOperation = Annotated[
    SetComponentProp
    | SetThemeToken
    | InsertComponent
    | RemoveComponent
    | MoveComponent
    | SetPageSeo
    | AddPage
    | MovePage
    | SetNavigationVisibility,
    Field(discriminator="kind"),
]


class EditPlan(Schema):
    summary: str = Field(min_length=1, max_length=240)
    operations: list[EditorOperation] = Field(min_length=1, max_length=30)


class ManualEditRequest(Schema):
    operation_id: UUID
    base_revision: int = Field(ge=1)
    scope: Literal["PAGE", "WEBSITE"]
    selected_page_id: UUID | None = None
    summary: str = Field(min_length=1, max_length=240)
    operations: list[EditorOperation] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def selected_page_matches_scope(self) -> ManualEditRequest:
        if self.scope == "PAGE" and self.selected_page_id is None:
            raise ValueError("PAGE scope requires selected_page_id")
        return self


class AiEditRequest(Schema):
    operation_id: UUID
    base_revision: int = Field(ge=1)
    prompt: str = Field(min_length=3, max_length=1200)
    scope: Literal["PAGE", "WEBSITE"]
    selected_page_id: UUID | None = None

    @model_validator(mode="after")
    def selected_page_matches_scope(self) -> AiEditRequest:
        if self.scope == "PAGE" and self.selected_page_id is None:
            raise ValueError("PAGE scope requires selected_page_id")
        return self


class RestoreRequest(Schema):
    operation_id: UUID
    base_revision: int = Field(ge=1)


class RevisionResponse(Schema):
    id: UUID
    revision: int
    source: str
    edit_summary: str
    checksum: str
    created_at: datetime


class CreditResponse(Schema):
    balance: int
    allowance: int
    period_start: datetime
    period_end: datetime


class EditorStateResponse(Schema):
    website_id: UUID
    display_name: str
    status: str
    revision: int
    document: dict[str, object]
    revisions: list[RevisionResponse]
    credits: CreditResponse


class EditorMutationResponse(EditorStateResponse):
    operation_id: UUID
    source: Literal["MANUAL", "AI", "RESTORE"]
    summary: str
    credits_used: int


class AiUsageResponse(Schema):
    operation_id: UUID
    status: str
    provider: str
    model: str
    cost_credits: int
    usage: dict[str, int | float | str]
    latency_ms: int | None
    created_at: datetime


class AiUsageListResponse(Schema):
    items: list[AiUsageResponse]
