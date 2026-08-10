from __future__ import annotations

from copy import deepcopy

import pytest
from zylora_api.modules.templates import scaling
from zylora_api.modules.templates.fixtures import CURATED_CATALOG, INITIAL_CATALOG
from zylora_api.modules.templates.scaling import (
    SCALE_MILESTONES,
    SCALE_TARGET,
    _all_components,
    assert_scale_quality,
    assess_scale_quality,
    build_scaled_catalogue,
)


@pytest.mark.parametrize("milestone", SCALE_MILESTONES)
def test_every_scale_batch_is_valid_balanced_and_structurally_distinct(milestone: int) -> None:
    report = assert_scale_quality(build_scaled_catalogue(milestone))

    assert report.count == milestone
    assert report.categories == 10
    assert report.layouts >= min(10, milestone // 10)
    assert report.archetypes >= min(10, milestone // 10)
    assert report.page_counts == (1, 2, 3)


def test_full_curated_catalogue_exceeds_one_thousand_valid_templates() -> None:
    generated = build_scaled_catalogue()

    assert len(generated) == SCALE_TARGET
    assert len(CURATED_CATALOG) == len(INITIAL_CATALOG) + SCALE_TARGET
    assert len({item["slug"] for item in generated}) == SCALE_TARGET
    assert len({item["name"] for item in generated}) == SCALE_TARGET
    assert all(
        "TESTIMONIALS"
        not in {
            component["type"]
            for page in item["document"]["pages"]
            for component in page["components"]
        }
        for item in generated
    )


def test_scale_quality_rejects_superficial_duplicate_outputs() -> None:
    generated = build_scaled_catalogue(50)
    generated[1]["slug"] = generated[0]["slug"]

    report = assess_scale_quality(generated)

    assert report.valid is False
    assert "duplicate_slug" in report.errors


@pytest.mark.parametrize("limit", (0, SCALE_TARGET + 1))
def test_scale_builder_rejects_limits_outside_the_release_target(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be between"):
        build_scaled_catalogue(limit)


def test_scale_builder_returns_the_complete_catalogue_if_target_exceeds_source_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scaling, "SCALE_TARGET", SCALE_TARGET + 1)

    catalogue = scaling.build_scaled_catalogue(SCALE_TARGET + 1)

    assert len(catalogue) == SCALE_TARGET


def test_quality_gate_rejects_repetition_and_insufficient_structure() -> None:
    generated = deepcopy(build_scaled_catalogue(50))
    generated[1]["slug"] = generated[0]["slug"]
    generated[2]["name"] = generated[0]["name"]
    generated[3]["document"] = deepcopy(generated[0]["document"])
    for item in generated:
        item["category_slug"] = "single-category"
        item["tags"] = ["single-category"]
        item["document"]["pages"] = [item["document"]["pages"][0]]

    report = assess_scale_quality(generated)

    assert report.valid is False
    assert {
        "duplicate_slug",
        "duplicate_name",
        "duplicate_document",
        "insufficient_category_coverage",
        "insufficient_content_archetypes",
        "insufficient_layout_variation",
        "insufficient_site_map_variation",
    }.issubset(report.errors)


def test_quality_gate_rejects_invalid_and_unsafe_documents_and_assertion_path() -> None:
    invalid = deepcopy(build_scaled_catalogue(1))
    invalid[0]["document"]["schema_version"] = "not-supported"
    unsafe = deepcopy(build_scaled_catalogue(1))
    unsafe[0]["document"]["metadata"]["description"] = "<script>x</script>"

    assert "invalid_document" in assess_scale_quality(invalid).errors
    assert "unsubstantiated_or_unsafe_content" in assess_scale_quality(unsafe).errors
    with pytest.raises(ValueError, match="catalogue_empty"):
        assert_scale_quality([])


def test_component_walker_includes_nested_component_children() -> None:
    document = deepcopy(build_scaled_catalogue(1)[0]["document"])
    document["pages"][0]["components"][0]["children"].append(
        {"id": "nested", "type": "RICH_TEXT", "props": {}, "children": []}
    )

    component_ids = {component["id"] for component in _all_components(document)}

    assert "nested" in component_ids
