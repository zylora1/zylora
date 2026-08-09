from __future__ import annotations

import json
from pathlib import Path

from zylora_api.modules.templates.document import (
    COMPONENT_REGISTRY,
    REGISTRY_VERSION,
    SCHEMA_VERSION,
    TemplateDocument,
)

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "packages" / "template-schema"


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    schema = TemplateDocument.model_json_schema()
    schema["$id"] = "https://schemas.zylora.com/template-document/1.0.0.json"
    schema["x-zylora-schema-version"] = SCHEMA_VERSION
    registry = {
        "version": REGISTRY_VERSION,
        "components": {
            key: {
                "allowedProps": sorted(value.allowed_props),
                "requiredProps": sorted(value.required_props),
                "minChildren": value.min_children,
                "maxChildren": value.max_children,
                "requiredFeature": value.required_feature,
            }
            for key, value in sorted(COMPONENT_REGISTRY.items())
        },
    }
    (TARGET / "template-document.schema.json").write_text(
        json.dumps(schema, indent=2) + "\n", encoding="utf-8"
    )
    (TARGET / "component-registry.json").write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
