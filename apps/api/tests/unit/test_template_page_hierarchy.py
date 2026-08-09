from copy import deepcopy

from zylora_api.modules.templates.fixtures import CURATED_CATALOG
from zylora_api.modules.templates.validation import validate_document


def candidate() -> dict[str, object]:
    return deepcopy(CURATED_CATALOG[0]["document"])  # type: ignore[return-value]


def test_template_page_hierarchy_rejects_missing_parent() -> None:
    document = candidate()
    child = deepcopy(document["pages"][0])  # type: ignore[index]
    child.update(
        {
            "id": "child-page",
            "slug": "child",
            "label": "Child",
            "parent_page_id": "missing-page",
            "sort_order": 1,
            "is_home": False,
        }
    )
    document["pages"].append(child)  # type: ignore[union-attr]
    assert validate_document(document).valid is False


def test_template_page_hierarchy_rejects_multiple_or_nested_home() -> None:
    document = candidate()
    child = deepcopy(document["pages"][0])  # type: ignore[index]
    child.update(
        {
            "id": "child-page",
            "slug": "home",
            "label": "Child",
            "parent_page_id": None,
            "sort_order": 1,
            "is_home": True,
        }
    )
    document["pages"].append(child)  # type: ignore[union-attr]
    assert validate_document(document).valid is False


def test_template_page_hierarchy_rejects_cycles() -> None:
    document = candidate()
    child = deepcopy(document["pages"][0])  # type: ignore[index]
    child.update(
        {
            "id": "child-page",
            "slug": "child",
            "label": "Child",
            "parent_page_id": "home-page",
            "sort_order": 1,
            "is_home": False,
        }
    )
    document["pages"].append(child)  # type: ignore[union-attr]
    document["pages"][0]["parent_page_id"] = "child-page"  # type: ignore[index]
    document["pages"][0]["is_home"] = False  # type: ignore[index]
    assert validate_document(document).valid is False
