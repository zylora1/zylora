from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    heads = scripts.get_heads()
    if heads != ["20260810_0005"]:
        raise SystemExit(f"expected one Phase 4 migration head, found: {heads}")


if __name__ == "__main__":
    main()
