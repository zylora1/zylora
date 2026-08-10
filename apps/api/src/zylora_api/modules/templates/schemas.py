from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemplateCreateRequest(Schema):
    slug: Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    summary: Annotated[str, Field(min_length=1, max_length=500)]
    category_slug: Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)]
    category_name: Annotated[str, Field(min_length=1, max_length=100)]
    category_description: Annotated[str, Field(min_length=1, max_length=300)]
    tags: Annotated[list[str], Field(max_length=12)] = []
    featured_order: Annotated[int, Field(ge=0, le=10000)] = 1000


class TemplateMetadataUpdateRequest(Schema):
    name: Annotated[str | None, Field(min_length=1, max_length=120)] = None
    summary: Annotated[str | None, Field(min_length=1, max_length=500)] = None
    category_slug: Annotated[
        str | None, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    ] = None
    category_name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    category_description: Annotated[str | None, Field(min_length=1, max_length=300)] = None
    tags: Annotated[list[str] | None, Field(max_length=12)] = None
    featured_order: Annotated[int | None, Field(ge=0, le=10000)] = None


class VersionCreateRequest(Schema):
    document: dict[str, Any]


class ReasonRequest(Schema):
    reason: Annotated[str, Field(min_length=8, max_length=500)]


class TemplateSummary(Schema):
    id: UUID
    slug: str
    name: str
    summary: str
    category: str
    category_slug: str
    tags: list[str]
    features: list[str]
    version: int
    status: str
    featured_order: int


class CatalogResponse(Schema):
    items: list[TemplateSummary]
    next_cursor: str | None


class PreviewResponse(Schema):
    slug: str
    name: str
    version: int
    document: dict[str, Any]
    checksum: str


class VersionResponse(Schema):
    id: UUID
    version: int
    status: str
    checksum: str
    validation_summary: dict[str, Any] | None
    created_at: datetime


class AdminTemplateResponse(Schema):
    id: UUID
    slug: str
    name: str
    summary: str
    status: str
    category: str
    tags: list[str]
    versions: list[VersionResponse]


class AdminTemplateListResponse(Schema):
    items: list[AdminTemplateResponse]
