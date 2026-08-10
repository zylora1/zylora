from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from zylora_api.db.base import Base

blog_post_categories = Table(
    "blog_post_categories",
    Base.metadata,
    Column(
        "post_id",
        PGUUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        PGUUID(as_uuid=True),
        ForeignKey("blog_categories.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)
blog_post_tags = Table(
    "blog_post_tags",
    Base.metadata,
    Column(
        "post_id",
        PGUUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        PGUUID(as_uuid=True),
        ForeignKey("blog_tags.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class BlogPost(Base):
    __tablename__ = "blog_posts"
    __table_args__ = (
        CheckConstraint(
            "state IN ('DRAFT','READY','SCHEDULED','PUBLISHED','ARCHIVED')",
            name="ck_blog_posts_state",
        ),
        UniqueConstraint("slug", name="uq_blog_posts_slug"),
        Index("ix_blog_posts_publication", "state", "published_at", "scheduled_at"),
    )
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    author_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    excerpt: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    featured_image_url: Mapped[str | None] = mapped_column(String(1000))
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="DRAFT")
    seo_title: Mapped[str | None] = mapped_column(String(180))
    meta_description: Mapped[str | None] = mapped_column(String(320))
    canonical_url: Mapped[str | None] = mapped_column(String(1000))
    og_title: Mapped[str | None] = mapped_column(String(180))
    og_description: Mapped[str | None] = mapped_column(String(320))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BlogPostVersion(Base):
    __tablename__ = "blog_post_versions"
    __table_args__ = (UniqueConstraint("post_id", "version", name="uq_blog_post_versions_number"),)
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    post_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("blog_posts.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BlogCategory(Base):
    __tablename__ = "blog_categories"
    __table_args__ = (UniqueConstraint("slug", name="uq_blog_categories_slug"),)
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)


class BlogTag(Base):
    __tablename__ = "blog_tags"
    __table_args__ = (UniqueConstraint("slug", name="uq_blog_tags_slug"),)
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
