"""Run the local FastAPI service with a psycopg-compatible event loop on Windows."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, cast

import uvicorn


def main() -> None:
    loop_factory: str | type[asyncio.AbstractEventLoop]
    if sys.platform == "win32":
        loop_factory = asyncio.SelectorEventLoop
    else:
        loop_factory = "auto"

    uvicorn.run(
        "zylora_api.app:create_app",
        factory=True,
        host=os.getenv("ZYLORA_API_HOST", "127.0.0.1"),
        port=int(os.getenv("ZYLORA_API_PORT", "8000")),
        reload=os.getenv("ZYLORA_API_RELOAD", "0" if sys.platform == "win32" else "1") == "1",
        loop=cast(Any, loop_factory),
    )


if __name__ == "__main__":
    main()
