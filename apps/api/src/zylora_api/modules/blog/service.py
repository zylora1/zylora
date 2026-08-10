from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from re import fullmatch
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.blog_models import (
    BlogCategory,
    BlogPost,
    BlogPostVersion,
    BlogTag,
    blog_post_categories,
    blog_post_tags,
)
from zylora_api.modules.templates.service import problem

SLUG_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"


@dataclass(frozen=True)
class BlogPostSummary:
    id: UUID
    title: str
    slug: str
    excerpt: str
    state: str
    scheduled_at: datetime | None
    published_at: datetime | None
    categories: list[str]
    tags: list[str]


class BlogService:
    """Canonical Blog aggregate writer and safe public read projection."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, actor_user_id: UUID, payload: dict[str, object]) -> BlogPost:
        values = self._validated_values(payload)
        existing = await self.session.scalar(
            select(BlogPost.id).where(BlogPost.slug == values["slug"])
        )
        if existing:
            raise problem(409, "blog_slug_conflict", "That Blog URL is already in use.")
        post = BlogPost(author_user_id=actor_user_id, **values)
        self.session.add(post)
        await self.session.flush()
        await self._set_taxonomy(post.id, payload)
        return post

    async def update(self, post_id: UUID, *, payload: dict[str, object]) -> BlogPost:
        post = await self._locked_post(post_id)
        if post.state not in {"DRAFT", "READY"}:
            raise problem(
                409,
                "blog_post_not_editable",
                "Published or scheduled Blog posts cannot be edited directly.",
            )
        values = self._validated_values(payload)
        conflict = await self.session.scalar(
            select(BlogPost.id).where(BlogPost.slug == values["slug"], BlogPost.id != post.id)
        )
        if conflict:
            raise problem(409, "blog_slug_conflict", "That Blog URL is already in use.")
        for key, value in values.items():
            setattr(post, key, value)
        post.version += 1
        await self._set_taxonomy(post.id, payload)
        return post

    async def ready(self, post_id: UUID) -> BlogPost:
        post = await self._locked_post(post_id)
        if post.state != "DRAFT":
            raise problem(409, "blog_post_not_draft", "Only draft Blog posts can be prepared.")
        self._validate_post(post)
        post.state, post.version = "READY", post.version + 1
        return post

    async def publish(self, post_id: UUID, *, correlation_id: str) -> BlogPost:
        post = await self._locked_post(post_id)
        if post.state not in {"READY", "SCHEDULED"}:
            raise problem(
                409, "blog_post_not_publishable", "Prepare the Blog post before publishing it."
            )
        self._validate_post(post)
        now = datetime.now(UTC)
        post.state, post.published_at, post.scheduled_at = "PUBLISHED", now, None
        post.version += 1
        self.session.add(
            BlogPostVersion(
                post_id=post.id,
                author_user_id=post.author_user_id,
                version=post.version,
                rendered_html=self.render_html(post.content),
            )
        )
        return post

    async def schedule(self, post_id: UUID, when: datetime) -> BlogPost:
        post = await self._locked_post(post_id)
        if post.state not in {"READY", "SCHEDULED"}:
            raise problem(
                409, "blog_post_not_schedulable", "Prepare the Blog post before scheduling it."
            )
        self._validate_post(post)
        if when.tzinfo is None or when <= datetime.now(UTC):
            raise problem(
                422, "blog_schedule_invalid", "Choose a future, timezone-aware publication time."
            )
        post.state, post.scheduled_at, post.version = "SCHEDULED", when, post.version + 1
        return post

    async def unpublish(self, post_id: UUID) -> BlogPost:
        post = await self._locked_post(post_id)
        if post.state != "PUBLISHED":
            raise problem(
                409, "blog_post_not_published", "Only published Blog posts can be unpublished."
            )
        post.state, post.published_at, post.version = "DRAFT", None, post.version + 1
        return post

    async def due_post_ids(self, limit: int) -> list[UUID]:
        return list(
            (
                await self.session.scalars(
                    select(BlogPost.id)
                    .where(
                        BlogPost.state == "SCHEDULED", BlogPost.scheduled_at <= datetime.now(UTC)
                    )
                    .order_by(BlogPost.scheduled_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )

    async def public_list(self, limit: int = 50) -> list[BlogPostSummary]:
        rows = list(
            (
                await self.session.scalars(
                    select(BlogPost)
                    .where(BlogPost.state == "PUBLISHED")
                    .order_by(BlogPost.published_at.desc())
                    .limit(limit)
                )
            ).all()
        )
        return [await self.summary(row) for row in rows]

    async def public_get(self, slug: str) -> BlogPost:
        post = await self.session.scalar(
            select(BlogPost).where(BlogPost.slug == slug, BlogPost.state == "PUBLISHED")
        )
        if not post:
            raise problem(404, "blog_post_not_found", "Blog post not found.")
        return post

    async def list_admin(self, limit: int = 50) -> list[BlogPostSummary]:
        rows = list(
            (
                await self.session.scalars(
                    select(BlogPost).order_by(BlogPost.updated_at.desc()).limit(limit)
                )
            ).all()
        )
        return [await self.summary(row) for row in rows]

    async def summary(self, post: BlogPost) -> BlogPostSummary:
        categories = list(
            (
                await self.session.scalars(
                    select(BlogCategory.name)
                    .join(
                        blog_post_categories, BlogCategory.id == blog_post_categories.c.category_id
                    )
                    .where(blog_post_categories.c.post_id == post.id)
                    .order_by(BlogCategory.name)
                )
            ).all()
        )
        tags = list(
            (
                await self.session.scalars(
                    select(BlogTag.name)
                    .join(blog_post_tags, BlogTag.id == blog_post_tags.c.tag_id)
                    .where(blog_post_tags.c.post_id == post.id)
                    .order_by(BlogTag.name)
                )
            ).all()
        )
        return BlogPostSummary(
            post.id,
            post.title,
            post.slug,
            post.excerpt,
            post.state,
            post.scheduled_at,
            post.published_at,
            categories,
            tags,
        )

    async def _locked_post(self, post_id: UUID) -> BlogPost:
        post = await self.session.scalar(
            select(BlogPost).where(BlogPost.id == post_id).with_for_update()
        )
        if not post:
            raise problem(404, "blog_post_not_found", "Blog post not found.")
        return post

    async def _set_taxonomy(self, post_id: UUID, payload: dict[str, object]) -> None:
        category_names = self._names(payload.get("categories"))
        tag_names = self._names(payload.get("tags"))
        await self.session.execute(
            blog_post_categories.delete().where(blog_post_categories.c.post_id == post_id)
        )
        await self.session.execute(
            blog_post_tags.delete().where(blog_post_tags.c.post_id == post_id)
        )
        for name in category_names:
            category = await self._taxonomy(BlogCategory, name)
            await self.session.execute(
                blog_post_categories.insert().values(post_id=post_id, category_id=category.id)
            )
        for name in tag_names:
            tag = await self._taxonomy(BlogTag, name)
            await self.session.execute(
                blog_post_tags.insert().values(post_id=post_id, tag_id=tag.id)
            )

    async def _taxonomy(
        self, model: type[BlogCategory] | type[BlogTag], name: str
    ) -> BlogCategory | BlogTag:
        slug = self.slugify(name)
        current = await self.session.scalar(select(model).where(model.slug == slug))
        if current:
            return cast(BlogCategory | BlogTag, current)
        current = model(name=name, slug=slug)
        self.session.add(current)
        await self.session.flush()
        return current

    def _validated_values(self, payload: dict[str, object]) -> dict[str, object]:
        title = self._string(payload, "title", 180)
        slug = self._string(payload, "slug", 120)
        excerpt = self._string(payload, "excerpt", 500)
        content = self._string(payload, "content", 50_000)
        if not fullmatch(SLUG_PATTERN, slug):
            raise problem(
                422,
                "blog_slug_invalid",
                "Use lowercase letters, numbers, and hyphens for the Blog URL.",
            )
        featured = self._optional_url(payload.get("featured_image_url"))
        canonical = self._optional_url(payload.get("canonical_url"))
        return {
            "title": title,
            "slug": slug,
            "excerpt": excerpt,
            "content": content,
            "featured_image_url": featured,
            "seo_title": self._optional_string(payload.get("seo_title"), 180),
            "meta_description": self._optional_string(payload.get("meta_description"), 320),
            "canonical_url": canonical,
            "og_title": self._optional_string(payload.get("og_title"), 180),
            "og_description": self._optional_string(payload.get("og_description"), 320),
        }

    @staticmethod
    def render_html(content: str) -> str:
        blocks = [part.strip() for part in content.split("\n\n") if part.strip()]
        rendered: list[str] = []
        for block in blocks:
            if block.startswith("## "):
                rendered.append(f"<h2>{escape(block[3:])}</h2>")
            elif block.startswith("# "):
                rendered.append(f"<h2>{escape(block[2:])}</h2>")
            else:
                rendered.append(f"<p>{escape(block).replace(chr(10), '<br>')}</p>")
        return "".join(rendered)

    @staticmethod
    def slugify(value: str) -> str:
        slug = "-".join(
            "".join(char for char in part.casefold() if char.isalnum()) for part in value.split()
        )
        if not fullmatch(SLUG_PATTERN, slug or ""):
            raise problem(422, "blog_taxonomy_invalid", "Blog category and tag names are invalid.")
        return slug

    @staticmethod
    def _string(payload: dict[str, object], key: str, maximum: int) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
            raise problem(422, "blog_content_invalid", f"Blog {key.replace('_', ' ')} is invalid.")
        return value.strip()

    @staticmethod
    def _optional_string(value: object, maximum: int) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
            raise problem(422, "blog_content_invalid", "Blog SEO metadata is invalid.")
        return value.strip()

    @staticmethod
    def _optional_url(value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.startswith("https://") or len(value) > 1000:
            raise problem(
                422, "blog_url_invalid", "Blog image and canonical URLs must be HTTPS URLs."
            )
        return value

    @staticmethod
    def _names(value: object) -> list[str]:
        if value is None:
            return []
        if (
            not isinstance(value, list)
            or len(value) > 12
            or any(not isinstance(item, str) or not 1 <= len(item.strip()) <= 80 for item in value)
        ):
            raise problem(422, "blog_taxonomy_invalid", "Blog categories or tags are invalid.")
        return list(dict.fromkeys(item.strip() for item in value))

    def _validate_post(self, post: BlogPost) -> None:
        self._validated_values(
            {
                "title": post.title,
                "slug": post.slug,
                "excerpt": post.excerpt,
                "content": post.content,
                "featured_image_url": post.featured_image_url,
                "seo_title": post.seo_title,
                "meta_description": post.meta_description,
                "canonical_url": post.canonical_url,
                "og_title": post.og_title,
                "og_description": post.og_description,
            }
        )
