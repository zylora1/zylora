from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from zylora_api.api.templates import admin_list, catalog, categories, detail, preview
from zylora_api.db.template_models import Template, TemplateCategory, TemplateVersion
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.fixtures import CURATED_CATALOG


class Rows:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class Result(Rows):
    def one_or_none(self) -> object | None:
        return self.values[0] if self.values else None


class FakeSession:
    def __init__(
        self,
        execute_rows: list[object],
        scalar_batches: list[list[object]] | None = None,
        category: TemplateCategory | None = None,
    ) -> None:
        self.execute_rows = execute_rows
        self.scalar_batches = scalar_batches or []
        self.category = category
        self.commits = 0

    async def execute(self, statement: object) -> Result:
        return Result(self.execute_rows)

    async def scalars(self, statement: object) -> Rows:
        return Rows(self.scalar_batches.pop(0) if self.scalar_batches else ["clinic"])

    async def get(self, model: object, model_id: object) -> object | None:
        return self.category

    async def commit(self) -> None:
        self.commits += 1


def models() -> tuple[Template, TemplateVersion, TemplateCategory]:
    now = datetime.now(UTC)
    category = TemplateCategory(
        id=uuid4(),
        slug="health",
        name="Health",
        description="Health sites",
        active=True,
        sort_order=0,
    )
    version = TemplateVersion(
        id=uuid4(),
        template_id=uuid4(),
        version=1,
        status="PUBLISHED",
        document=CURATED_CATALOG[0]["document"],
        checksum="a" * 64,
        schema_version="1.0.0",
        registry_version="1.0.0",
        created_by=uuid4(),
        created_at=now,
    )
    template = Template(
        id=version.template_id,
        slug="haven",
        name="Haven",
        summary="Calm clinic",
        category_id=category.id,
        status="ACTIVE",
        featured_order=1,
        current_published_version_id=version.id,
        created_by=uuid4(),
        created_at=now,
        updated_at=now,
    )
    return template, version, category


async def test_catalogue_filters_paginates_and_serializes_published_rows() -> None:
    template, version, category = models()
    session = FakeSession([(template, version, category), (template, version, category)])
    result = await catalog(
        session,
        AuthCrypto("template-http-secret-long-enough-123"),
        query="Haven",
        category="health",
        tag="clinic",
        feature="LEAD_CAPTURE",
        sort="name",
        limit=1,
    )

    assert result.items[0].slug == "haven"
    assert result.items[0].tags == ["clinic"]
    assert result.next_cursor is not None


async def test_public_detail_and_preview_return_only_available_rows() -> None:
    template, version, category = models()
    summary = await detail("haven", FakeSession([(template, version, category)]))
    rendered = await preview("haven", 1, FakeSession([(template, version)]))

    assert summary.category == "Health"
    assert rendered.document["schema_version"] == "1.0.0"
    with pytest.raises(AuthProblem) as missing_detail:
        await detail("missing", FakeSession([]))
    with pytest.raises(AuthProblem) as missing_preview:
        await preview("missing", 1, FakeSession([]))
    assert missing_detail.value.code == "template_not_found"
    assert missing_preview.value.code == "template_preview_not_found"


async def test_admin_list_includes_versions_and_commits_read_session() -> None:
    template, version, category = models()
    session = FakeSession([], scalar_batches=[[template], [version], ["clinic"]], category=category)
    result = await admin_list(object(), session)  # type: ignore[arg-type]

    assert result.items[0].versions[0].status == "PUBLISHED"
    assert result.items[0].tags == ["clinic"]
    assert session.commits == 1


async def test_public_categories_include_only_catalogue_filter_values() -> None:
    _, _, category = models()
    result = await categories(FakeSession([], scalar_batches=[[category]]))

    assert [(item.slug, item.name) for item in result] == [("health", "Health")]
