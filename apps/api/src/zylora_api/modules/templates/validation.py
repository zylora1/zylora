from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError
from zylora_api.modules.templates.document import COMPONENT_REGISTRY, TemplateDocument

VALIDATOR_VERSION = "1.0.0"
MAX_DOCUMENT_BYTES = 256_000
MAX_COMPONENTS = 400
MAX_DEPTH = 8


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    checksum: str
    errors: tuple[dict[str, str], ...]
    warnings: tuple[dict[str, str], ...]
    computed_requirements: tuple[str, ...]

    def summary(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "validatorVersion": VALIDATOR_VERSION,
            "checksum": self.checksum,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "computedRequirements": list(self.computed_requirements),
            "checks": [
                "schema_registry_limits",
                "asset_references",
                "links_forms",
                "responsive_contract",
                "editor_compatibility",
                "accessibility_contract",
                "runtime_safety",
                "seo_contract",
                "performance_budget",
            ],
        }


def canonical_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def document_checksum(document: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(document)).hexdigest()


def _error(code: str, path: str) -> dict[str, str]:
    return {"code": code, "path": path}


def validate_document(raw: dict[str, Any]) -> ValidationResult:
    checksum = document_checksum(raw)
    errors: list[dict[str, str]] = []
    requirements: set[str] = set()
    if len(canonical_bytes(raw)) > MAX_DOCUMENT_BYTES:
        errors.append(_error("document_too_large", "$"))
    try:
        document = TemplateDocument.model_validate(raw)
    except ValidationError as exc:
        for issue in exc.errors(include_url=False, include_context=False):
            errors.append(_error(str(issue["type"]), ".".join(map(str, issue["loc"]))))
        return ValidationResult(False, checksum, tuple(errors), (), ())

    seen_ids: set[str] = set()
    count = 0
    declared_assets = {asset.id for asset in document.assets}
    page_slugs = {page.slug for page in document.pages}

    def visit(component: Any, path: str, depth: int) -> None:
        nonlocal count
        count += 1
        if depth > MAX_DEPTH:
            errors.append(_error("component_depth_exceeded", path))
        if component.id in seen_ids:
            errors.append(_error("duplicate_component_id", f"{path}.id"))
        seen_ids.add(component.id)
        entry = COMPONENT_REGISTRY.get(component.type)
        if entry is None:
            errors.append(_error("unknown_component_type", f"{path}.type"))
        else:
            unknown = set(component.props) - entry.allowed_props
            missing = entry.required_props - set(component.props)
            if unknown:
                errors.append(_error("unknown_component_props", f"{path}.props"))
            if missing:
                errors.append(_error("missing_component_props", f"{path}.props"))
            if not entry.min_children <= len(component.children) <= entry.max_children:
                errors.append(_error("invalid_child_count", f"{path}.children"))
            if entry.required_feature:
                requirements.add(entry.required_feature)
        blob = json.dumps(component.props, sort_keys=True).lower()
        if any(
            token in blob
            for token in ("<script", "javascript:", "data:text/html", "onerror=", "onclick=")
        ):
            errors.append(_error("executable_content_rejected", f"{path}.props"))
        asset_id = component.props.get("assetId")
        asset_ids = component.props.get("assetIds", [])
        for referenced in ([asset_id] if asset_id else []) + (
            asset_ids if isinstance(asset_ids, list) else []
        ):
            if referenced not in declared_assets:
                errors.append(_error("undeclared_asset", f"{path}.props"))
        for key, value in component.props.items():
            if key.lower().endswith("link") and isinstance(value, dict):
                kind, target = value.get("kind"), value.get("target", "")
                if kind == "EXTERNAL" and urlparse(target).scheme not in {"https"}:
                    errors.append(_error("unsafe_external_link", f"{path}.props.{key}"))
                if kind == "PAGE" and target not in page_slugs:
                    errors.append(_error("missing_page_link", f"{path}.props.{key}"))
        for index, child in enumerate(component.children):
            visit(child, f"{path}.children.{index}", depth + 1)

    for page_index, page in enumerate(document.pages):
        headings = 0
        for component_index, component in enumerate(page.components):
            visit(component, f"pages.{page_index}.components.{component_index}", 1)
            if component.type == "HEADING" and component.props.get("level") == 1:
                headings += 1
            if component.type == "HERO":
                headings += 1
        if headings != 1:
            errors.append(_error("exactly_one_page_h1_required", f"pages.{page_index}.components"))
    if count > MAX_COMPONENTS:
        errors.append(_error("component_count_exceeded", "pages"))
    if set(document.requirements) != requirements:
        errors.append(_error("requirements_not_recomputed", "requirements"))
    return ValidationResult(not errors, checksum, tuple(errors), (), tuple(sorted(requirements)))
