from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.fixtures import CURATED_CATALOG
from zylora_api.modules.templates.schemas import TemplateMetadataUpdateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.templates.validation import document_checksum, validate_document


def document() -> dict[str, object]:
    return deepcopy(CURATED_CATALOG[0]["document"])  # type: ignore[return-value]


def test_curated_template_passes_canonical_validation() -> None:
    candidate = document()
    result = validate_document(candidate)

    assert result.valid is True
    assert result.errors == ()
    assert result.computed_requirements == ("LEAD_CAPTURE",)
    assert result.checksum == document_checksum(candidate)
    assert len(result.summary()["checks"]) == 9


def test_validator_rejects_unknown_props_executable_content_and_requirement_drift() -> None:
    candidate = document()
    hero = candidate["pages"][0]["components"][1]  # type: ignore[index]
    hero["props"]["rawHtml"] = "<script>alert(1)</script>"  # type: ignore[index]
    candidate["requirements"] = []

    result = validate_document(candidate)
    codes = {issue["code"] for issue in result.errors}

    assert result.valid is False
    assert {
        "unknown_component_props",
        "executable_content_rejected",
        "requirements_not_recomputed",
    }.issubset(codes)


def test_validator_rejects_duplicate_ids_unsafe_links_and_missing_h1() -> None:
    candidate = document()
    components = candidate["pages"][0]["components"]  # type: ignore[index]
    components[1]["id"] = components[0]["id"]
    components[1]["type"] = "CARD"
    components[1]["props"] = {
        "heading": "Unsafe",
        "body": "No",
        "link": {"kind": "EXTERNAL", "target": "javascript:alert(1)"},
    }

    result = validate_document(candidate)
    codes = {issue["code"] for issue in result.errors}

    assert {
        "duplicate_component_id",
        "executable_content_rejected",
        "exactly_one_page_h1_required",
    }.issubset(codes)


def test_document_checksum_is_order_independent_and_content_sensitive() -> None:
    first = document()
    reordered = dict(reversed(list(first.items())))
    changed = deepcopy(first)
    changed["metadata"]["name"] = "Changed"  # type: ignore[index]

    assert document_checksum(first) == document_checksum(reordered)
    assert document_checksum(first) != document_checksum(changed)


@pytest.mark.asyncio
async def test_template_unpublish_and_restore_keep_validation_gate() -> None:
    service = TemplateService(
        SimpleNamespace(), AuthCrypto("template-phase12-test-secret-long-enough")
    )
    template = SimpleNamespace(current_published_version_id=uuid4(), status="ACTIVE")
    version = SimpleNamespace(id=template.current_published_version_id, status="PUBLISHED")

    async def template_lookup(_: UUID) -> object:
        return template

    async def version_lookup(_: UUID, __: int) -> object:
        return version

    service._template = template_lookup  # type: ignore[method-assign]
    service._version = version_lookup  # type: ignore[method-assign]
    unpublished = await service.unpublish(uuid4(), 1)
    assert unpublished.status == "DEPRECATED"
    assert template.current_published_version_id is None and template.status == "DRAFT"

    service._validation_current = lambda _: True  # type: ignore[method-assign]
    service.session.scalar = AsyncMock(return_value=None)  # type: ignore[attr-defined]
    restored = await service.restore(uuid4(), 1)
    assert restored.status == "PUBLISHED"
    assert template.current_published_version_id == version.id and template.status == "ACTIVE"


@pytest.mark.asyncio
async def test_template_restore_rejects_stale_validation() -> None:
    service = TemplateService(
        SimpleNamespace(), AuthCrypto("template-phase12-test-secret-long-enough")
    )
    template = SimpleNamespace(current_published_version_id=None, status="DEPRECATED")
    version = SimpleNamespace(id=uuid4(), status="DEPRECATED")

    async def template_lookup(_: UUID) -> object:
        return template

    async def version_lookup(_: UUID, __: int) -> object:
        return version

    service._template = template_lookup  # type: ignore[method-assign]
    service._version = version_lookup  # type: ignore[method-assign]
    service._validation_current = lambda _: False  # type: ignore[method-assign]
    with pytest.raises(AuthProblem, match="current successful validation"):
        await service.restore(uuid4(), 1)


class MetadataSession:
    def __init__(self, template: object, scalar_values: list[object]) -> None:
        self.template = template
        self.scalar_values = scalar_values
        self.added: list[object] = []
        self.executed = 0
        self.flushed = 0

    async def get(self, _: object, __: object) -> object:
        return self.template

    async def scalar(self, _: object) -> object:
        return self.scalar_values.pop(0)

    async def execute(self, _: object) -> None:
        self.executed += 1

    async def flush(self) -> None:
        self.flushed += 1

    def add(self, item: object) -> None:
        self.added.append(item)


@pytest.mark.asyncio
async def test_template_metadata_updates_existing_category_and_tags() -> None:
    template = SimpleNamespace(
        id=uuid4(),
        name="Before",
        summary="Before summary",
        featured_order=1000,
        category_id=uuid4(),
    )
    category = SimpleNamespace(id=uuid4())
    tag = SimpleNamespace(id=uuid4())
    session = MetadataSession(template, [category, tag])
    service = TemplateService(session, AuthCrypto("template-phase12-test-secret-long-enough"))

    result = await service.update_metadata(
        template.id,
        TemplateMetadataUpdateRequest(
            name="After",
            summary="After summary",
            category_slug="agency",
            tags=["premium"],
            featured_order=3,
        ),
    )

    assert result is template
    assert (template.name, template.summary, template.category_id, template.featured_order) == (
        "After",
        "After summary",
        category.id,
        3,
    )
    assert session.executed == 1 and len(session.added) == 1 and session.flushed == 1


@pytest.mark.asyncio
async def test_template_metadata_requires_new_category_details() -> None:
    template = SimpleNamespace(id=uuid4(), category_id=uuid4())
    session = MetadataSession(template, [None])
    service = TemplateService(session, AuthCrypto("template-phase12-test-secret-long-enough"))

    with pytest.raises(AuthProblem, match="name and description"):
        await service.update_metadata(
            template.id,
            TemplateMetadataUpdateRequest(category_slug="new-category"),
        )
