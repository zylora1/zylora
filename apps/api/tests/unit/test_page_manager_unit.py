from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from zylora_api.db.website_models import WebsitePage
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.websites.service import (
    build_navigation,
    page_paths,
    validate_page_slug,
)


def pages_for_size(count: int) -> list[WebsitePage]:
    website_id = uuid4()
    now = datetime.now(UTC)
    pages: list[WebsitePage] = []
    root_ids: dict[int, object] = {}
    for index in range(count):
        page_id = uuid4()
        group = index // 10
        is_home = index == 0
        if index and index % 10 == 1:
            root_ids[group] = page_id
        parent_id = None
        if index > 1 and index % 10 != 1:
            parent_id = root_ids.get(group)
        pages.append(
            WebsitePage(
                id=page_id,
                website_id=website_id,
                source_template_page_id=f"page-{index}",
                parent_page_id=parent_id,
                name="Home" if is_home else f"Page {index}",
                slug="" if is_home else f"page-{index}",
                sort_order=index,
                is_home=is_home,
                show_in_navigation=index % 7 != 0 or is_home,
                status="DRAFT",
                content={"components": []},
                seo={},
                created_at=now,
                updated_at=now,
            )
        )
    return pages


def count_navigation(nodes: list[dict[str, object]]) -> int:
    return sum(
        1 + count_navigation(node["children"])  # type: ignore[arg-type]
        for node in nodes
    )


@pytest.mark.parametrize("count", [1, 5, 30, 100])
def test_page_tree_and_navigation_scale_without_flat_card_assumptions(count: int) -> None:
    pages = pages_for_size(count)
    paths = page_paths(pages)
    assert len(paths) == count
    assert paths[pages[0].id] == "/"
    assert count_navigation(build_navigation(pages)) == sum(
        page.show_in_navigation for page in pages
    )
    if count >= 30:
        nested = next(page for page in pages if page.parent_page_id is not None)
        assert paths[nested.id].count("/") == 2


def test_navigation_visibility_is_distinct_from_structure() -> None:
    pages = pages_for_size(5)
    parent = next(page for page in pages if page.source_template_page_id == "page-1")
    child = next(page for page in pages if page.parent_page_id == parent.id)
    parent.show_in_navigation = False
    navigation = build_navigation(pages)
    root_ids = {node["page_id"] for node in navigation}
    assert child.id in root_ids
    assert parent.id not in root_ids
    assert page_paths(pages)[child.id].startswith("/page-1/")


@pytest.mark.parametrize("slug", ["Two Words", "two_words", "-about", "about-", "about--team", ""])
def test_invalid_page_slugs_are_rejected_server_side(slug: str) -> None:
    with pytest.raises(AuthProblem) as rejected:
        validate_page_slug(slug, None)
    assert rejected.value.code == "invalid_page_slug"


@pytest.mark.parametrize("slug", ["app", "admin", "api", "templates", "login"])
def test_platform_root_slugs_are_reserved(slug: str) -> None:
    with pytest.raises(AuthProblem) as rejected:
        validate_page_slug(slug, None)
    assert rejected.value.code == "reserved_page_slug"
    assert validate_page_slug(slug, uuid4()) == slug
