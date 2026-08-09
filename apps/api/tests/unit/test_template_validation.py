from copy import deepcopy

from zylora_api.modules.templates.fixtures import CURATED_CATALOG
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
