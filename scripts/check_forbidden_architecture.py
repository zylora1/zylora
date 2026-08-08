from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPES = [ROOT / "apps", ROOT / "packages", ROOT / "infra", ROOT / ".github"]
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".toml", ".yml", ".yaml"}
IGNORED_PARTS = {
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
}
FORBIDDEN = re.compile(
    "|".join(
        [
            "pine" + "cone",
            "chro" + "ma",
            "craft" + r"\.js",
            "freelancer",
            "client[_ -]?admin",
            "support[_ -]?admin",
            "template[_ -]?admin",
            "marketing[_ -]?admin",
            "enable[_ -]?blank[_ -]?canvas",
        ]
    ),
    re.IGNORECASE,
)
PLACEHOLDER = re.compile(r"\b(?:TODO|FIXME|NotImplementedError)\b")


def main() -> None:
    violations: list[str] = []
    for scope in SCOPES:
        if not scope.exists():
            continue
        for path in scope.rglob("*"):
            relative = path.relative_to(ROOT)
            if any(part in IGNORED_PARTS for part in relative.parts):
                continue
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            content = path.read_text(encoding="utf-8")
            for pattern, label in (
                (FORBIDDEN, "removed architecture"),
                (PLACEHOLDER, "placeholder"),
            ):
                match = pattern.search(content)
                if match:
                    violations.append(f"{relative}: {label}: {match.group(0)}")
    if violations:
        raise SystemExit("\n".join(violations))


if __name__ == "__main__":
    main()
