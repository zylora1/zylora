from __future__ import annotations

import json
from pathlib import Path

from zylora_api.app import create_app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "packages" / "contracts" / "openapi.json"


def main() -> None:
    schema = create_app().openapi()
    rendered = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
