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


def _chatbot_widget() -> str:
    """Platform-authored widget; all untrusted replies are inserted through textContent."""

    return """<aside class="zylora-chatbot" aria-label="Website assistant">
<button type="button" class="zylora-chatbot__open" aria-expanded="false">Ask this Website</button>
<section class="zylora-chatbot__panel" hidden aria-live="polite">
<div class="zylora-chatbot__messages"></div>
<form class="zylora-chatbot__form"><label>Ask a question<input name="message" maxlength="4000" required></label><button type="submit">Send</button></form>
</section></aside><script>(()=>{const root=document.querySelector('.zylora-chatbot');if(!root)return;const open=root.querySelector('.zylora-chatbot__open'),panel=root.querySelector('.zylora-chatbot__panel'),form=root.querySelector('.zylora-chatbot__form'),messages=root.querySelector('.zylora-chatbot__messages'),input=form.elements.message;let conversation;const add=(kind,value)=>{const line=document.createElement('p');line.className='zylora-chatbot__message zylora-chatbot__message--'+kind;line.textContent=value;messages.append(line);};const request=async(url,body)=>{const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.ok)throw new Error('The assistant is unavailable right now.');return response.json();};open.addEventListener('click',()=>{panel.hidden=!panel.hidden;open.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)input.focus();});form.addEventListener('submit',async(event)=>{event.preventDefault();const message=input.value.trim();if(!message)return;input.value='';add('visitor',message);try{if(!conversation)conversation=await request('/api/v1/public/chatbot/conversations',{});const reply=await request('/api/v1/public/chatbot/conversations/'+conversation.id+'/messages',{access_token:conversation.access_token,message});add('assistant',reply.answer);}catch(error){add('system','The assistant is unavailable right now. Please contact the business directly.');}});})();</script>"""


def _analytics_widget() -> str:
    """Platform-authored anonymous session instrumentation for the host-resolved public API."""

    return """<script>(()=>{const key='zylora.analytics.session';const create=()=>globalThis.crypto?.randomUUID?.().replaceAll('-','')||Math.random().toString(36).slice(2).padEnd(16,'0');let session;try{session=sessionStorage.getItem(key)||create();sessionStorage.setItem(key,session);}catch{session=create();}const event=create();fetch('/api/v1/public/analytics/page-views',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:event,session_id:session,page_path:location.pathname||'/'})}).catch(()=>{});})();</script>"""


def render_page(
    page: dict[str, Any],
    navigation: list[tuple[str, str]],
    *,
    include_chatbot: bool = True,
    include_analytics: bool = True,
) -> bytes:
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
    chatbot = _chatbot_widget() if include_chatbot else ""
    analytics = _analytics_widget() if include_analytics else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_text(seo.get("title")) or name}</title><meta name="description" content="{description}">'
        "<style>body{font-family:system-ui,sans-serif;margin:0;color:#17201e}nav,main{max-width:72rem;margin:auto;padding:1.25rem}nav{display:flex;gap:1rem;flex-wrap:wrap}section{padding:2rem 0}h1,h2{line-height:1.1}.zylora-chatbot{position:fixed;right:1rem;bottom:1rem;max-width:min(24rem,calc(100vw - 2rem));z-index:2}.zylora-chatbot__panel{margin-top:.5rem;padding:1rem;border:1px solid #d6ded9;border-radius:1rem;background:#fff;box-shadow:0 1rem 3rem #17201e33}.zylora-chatbot__messages{display:grid;gap:.5rem;max-height:16rem;overflow:auto}.zylora-chatbot__message{margin:0;padding:.55rem .7rem;border-radius:.65rem;background:#f1f5f2}.zylora-chatbot__message--visitor{background:#dbece1}.zylora-chatbot__form{display:grid;gap:.5rem;margin-top:.75rem}.zylora-chatbot__form input{display:block;width:100%;box-sizing:border-box;margin-top:.25rem;padding:.55rem}</style>"
        f"</head><body><nav>{nav}</nav><main><h1>{name}</h1>{content}</main>{chatbot}{analytics}</body></html>"
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
            data = render_page(page, navigation, include_chatbot=True)
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
