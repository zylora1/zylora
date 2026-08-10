from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BlogPostRequest(Schema):
    title: str = Field(min_length=1, max_length=180)
    slug: str = Field(min_length=1, max_length=120)
    excerpt: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=50_000)
    featured_image_url: str | None = Field(default=None, max_length=1000)
    categories: list[str] = Field(default_factory=list, max_length=12)
    tags: list[str] = Field(default_factory=list, max_length=12)
    seo_title: str | None = Field(default=None, max_length=180)
    meta_description: str | None = Field(default=None, max_length=320)
    canonical_url: str | None = Field(default=None, max_length=1000)
    og_title: str | None = Field(default=None, max_length=180)
    og_description: str | None = Field(default=None, max_length=320)


class BlogPostResponse(Schema):
    id: UUID
    title: str
    slug: str
    excerpt: str
    state: str
    scheduled_at: datetime | None
    published_at: datetime | None
    categories: list[str]
    tags: list[str]


class BlogScheduleRequest(Schema):
    scheduled_at: datetime
    reason: str = Field(min_length=3, max_length=500)


class BlogReasonRequest(Schema):
    reason: str = Field(min_length=3, max_length=500)


class PublicBlogPostResponse(BlogPostResponse):
    content_html: str
    featured_image_url: str | None
    seo_title: str | None
    meta_description: str | None
    canonical_path: str
    og_title: str | None
    og_description: str | None


class BlogSitemapItem(Schema):
    slug: str
    published_at: datetime
