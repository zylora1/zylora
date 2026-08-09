from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstantiateRequest(Schema):
    pass


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


class WebsiteResponse(Schema):
    id: UUID
    owner_user_id: UUID
    source_template_version_id: UUID
    display_name: str
    status: str
    pages: list[WebsitePageResponse]
    created_at: datetime
    updated_at: datetime


class WebsiteListResponse(Schema):
    items: list[WebsiteResponse]
