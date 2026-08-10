# ruff: noqa: E501
from __future__ import annotations

import html
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID

from zylora_api.storage.base import ObjectStorage


@dataclass(frozen=True)
class BuiltArtifact:
    manifest_key: str
    checksum: str


def _text(value: object) -> str:
    return html.escape(value if isinstance(value, str) else "", quote=True)


def _component_html(component: dict[str, Any]) -> str:
    raw_props = component.get("props")
    props: dict[str, Any] = raw_props if isinstance(raw_props, dict) else {}
    heading = _text(props.get("heading") or props.get("title"))
    body = _text(props.get("body") or props.get("text") or props.get("description"))
    raw_children = component.get("children")
    children: list[Any] = raw_children if isinstance(raw_children, list) else []
    nested = "".join(_component_html(item) for item in children if isinstance(item, dict))
    pieces = ["<section>"]
    if heading:
        pieces.append(f"<h2>{heading}</h2>")
    if body:
        pieces.append(f"<p>{body}</p>")
    pieces.append(nested)
    pieces.append("</section>")
    return "".join(pieces)


def render_page(page: dict[str, Any], navigation: list[tuple[str, str]]) -> bytes:
    name = _text(page.get("name") or page.get("label") or "Website")
    raw_seo = page.get("seo")
    seo: dict[str, Any] = raw_seo if isinstance(raw_seo, dict) else {}
    description = _text(seo.get("description"))
    raw_components = page.get("components")
    components: list[Any] = raw_components if isinstance(raw_components, list) else []
    nav = "".join(
        f'<a href="{html.escape(path, quote=True)}">{_text(label)}</a>'
        for label, path in navigation
    )
    content = "".join(_component_html(item) for item in components if isinstance(item, dict))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_text(seo.get("title")) or name}</title><meta name="description" content="{description}">'
        "<style>body{font-family:system-ui,sans-serif;margin:0;color:#17201e}nav,main{max-width:72rem;margin:auto;padding:1.25rem}nav{display:flex;gap:1rem;flex-wrap:wrap}section{padding:2rem 0}h1,h2{line-height:1.1}</style>"
        f"</head><body><nav>{nav}</nav><main><h1>{name}</h1>{content}</main></body></html>"
    ).encode()


class ArtifactBuilder:
    def __init__(self, storage: ObjectStorage) -> None:
        self.storage = storage

    def build(
        self, deployment_id: UUID, pages: list[dict[str, Any]], redirects: dict[str, str]
    ) -> BuiltArtifact:
        navigation = [
            (str(page.get("name") or page.get("label") or "Page"), str(page.get("path") or "/"))
            for page in pages
            if page.get("show_in_navigation") is True
        ]
        files: dict[str, str] = {}
        prefix = f"deployments/{deployment_id}"
        for page in pages:
            path = str(page.get("path") or "/")
            key_path = "index.html" if path == "/" else f"{path.strip('/')}/index.html"
            key = f"{prefix}/{key_path}"
            data = render_page(page, navigation)
            self.storage.put_bytes(key, data, "text/html; charset=utf-8")
            files[path] = key
        manifest = json.dumps(
            {"deployment_id": str(deployment_id), "files": files, "redirects": redirects},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        manifest_key = f"{prefix}/manifest.json"
        metadata = self.storage.put_bytes(manifest_key, manifest, "application/json")
        return BuiltArtifact(manifest_key, sha256(manifest).hexdigest() or metadata.checksum_sha256)
