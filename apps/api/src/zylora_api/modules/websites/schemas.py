from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstantiateRequest(Schema):
    pass


class PageCreateRequest(Schema):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=120)
    parent_page_id: UUID | None = None
    sort_order: int = Field(default=0, ge=0)
    show_in_navigation: bool = True
    status: Literal["DRAFT", "HIDDEN", "ARCHIVED"] = "DRAFT"
    seo: dict[str, str] = Field(default_factory=dict)


class PageUpdateRequest(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    parent_page_id: UUID | None = None
    sort_order: int | None = Field(default=None, ge=0)
    show_in_navigation: bool | None = None
    status: Literal["DRAFT", "HIDDEN", "ARCHIVED"] | None = None
    seo: dict[str, str] | None = None

    @model_validator(mode="after")
    def has_change(self) -> PageUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("At least one Page setting is required.")
        return self


class PageDeleteRequest(Schema):
    confirm: Literal[True]
    child_strategy: Literal["PROMOTE"]


class PagePathChangeResponse(Schema):
    page_id: UUID
    old_path: str
    new_path: str


class NavigationNodeResponse(Schema):
    page_id: UUID
    label: str
    path: str
    children: list[NavigationNodeResponse] = Field(default_factory=list)


class WebsitePageResponse(Schema):
    id: UUID
    parent_page_id: UUID | None
    name: str
    slug: str
    path: str
    sort_order: int
    is_home: bool
    show_in_navigation: bool
    status: str
    seo: dict[str, str]
    created_at: datetime
    updated_at: datetime


class WebsiteResponse(Schema):
    id: UUID
    owner_user_id: UUID
    source_template_version_id: UUID
    display_name: str
    status: str
    pages: list[WebsitePageResponse]
    navigation: list[NavigationNodeResponse]
    path_changes: list[PagePathChangeResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WebsiteListResponse(Schema):
    items: list[WebsiteResponse]
