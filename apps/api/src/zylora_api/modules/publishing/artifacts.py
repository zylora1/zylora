# ruff: noqa: E501
from __future__ import annotations

import html
import json
from dataclasses import dataclass
from hashlib import sha256
from importlib import resources
from typing import Any
from uuid import UUID

from zylora_api.storage.base import ObjectStorage

VISITOR_RUNTIME = (
    resources.files("zylora_api.modules.publishing")
    .joinpath("visitor_runtime.js")
    .read_text(encoding="utf-8")
)


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
    component_id = _text(component.get("id"))
    raw_children = component.get("children")
    children: list[Any] = raw_children if isinstance(raw_children, list) else []
    nested = "".join(_component_html(item) for item in children if isinstance(item, dict))
    if component.get("type") == "LEAD_FORM":
        submit_label = _text(props.get("submitLabel")) or "Send an enquiry"
        return (
            f'<section class="zylora-lead-inline" id="{component_id}">'
            f"<h2>{heading}</h2><p>{body}</p>"
            f'<button type="button" data-zylora-lead-open>{submit_label}</button></section>'
        )
    pieces = [f'<section id="{component_id}">' if component_id else "<section>"]
    if heading:
        pieces.append(f"<h2>{heading}</h2>")
    if body:
        pieces.append(f"<p>{body}</p>")
    pieces.append(nested)
    pieces.append("</section>")
    return "".join(pieces)


def _chatbot_widget(include_lead_action: bool) -> str:
    """Platform-authored Q&A widget; untrusted replies are inserted through textContent."""

    lead_action = (
        '<button type="button" class="zylora-chatbot__enquiry" data-zylora-lead-open>'
        "Send an enquiry</button>"
        if include_lead_action
        else ""
    )
    return f"""<aside class="zylora-chatbot" aria-label="Website assistant">
<button type="button" class="zylora-chatbot__open" aria-expanded="false">Ask this Website</button>
<section class="zylora-chatbot__panel" hidden aria-live="polite">
<div class="zylora-chatbot__messages"></div>
<form class="zylora-chatbot__form"><label>Ask a question<input name="message" maxlength="4000" required></label><button type="submit">Send</button></form>
{lead_action}</section></aside>"""


def _find_lead_form(pages: list[dict[str, Any]]) -> dict[str, Any] | None:
    def find(components: object) -> dict[str, Any] | None:
        if not isinstance(components, list):
            return None
        for component in components:
            if not isinstance(component, dict):
                continue
            if component.get("type") == "LEAD_FORM":
                return component
            nested = find(component.get("children"))
            if nested:
                return nested
        return None

    for page in pages:
        if lead_form := find(page.get("components")):
            return lead_form
    return None


def _lead_form_widget(component: dict[str, Any], turnstile_site_key: str | None) -> str:
    raw_props = component.get("props")
    props: dict[str, Any] = raw_props if isinstance(raw_props, dict) else {}
    raw_fields = props.get("fields")
    fields = raw_fields if isinstance(raw_fields, list) else []
    field_labels = {
        str(field.get("name")): _text(field.get("label"))
        for field in fields
        if isinstance(field, dict)
    }
    name_label = field_labels.get("name") or "Name"
    email_label = field_labels.get("email") or "Email"
    phone_label = field_labels.get("phone") or "Phone"
    enquiry_label = field_labels.get("enquiry") or field_labels.get("message") or "How can we help?"
    email = (
        f'<label>{email_label}<input name="email" type="email" autocomplete="email" '
        'maxlength="320"></label>'
        if "email" in field_labels
        else ""
    )
    phone = (
        f'<label>{phone_label}<input name="phone" type="tel" autocomplete="tel" '
        'maxlength="80"></label>'
        if "phone" in field_labels
        else ""
    )
    challenge = (
        f'<div class="cf-turnstile" data-sitekey="{_text(turnstile_site_key)}" '
        'data-action="lead_submission" data-callback="zyloraLeadTurnstile"></div>'
        if turnstile_site_key
        else ""
    )
    component_id = _text(component.get("id"))
    heading = _text(props.get("heading")) or "Send an enquiry"
    body = _text(props.get("body")) or "Share your details and the business can respond."
    consent = _text(props.get("consentText")) or "I agree to be contacted about this enquiry."
    submit = _text(props.get("submitLabel")) or "Send enquiry"
    return f"""<div data-zylora-lead-controller data-auto-delay="10000" data-lead-target="{component_id}" data-challenge-required="{str(bool(turnstile_site_key)).lower()}">
<dialog class="zylora-lead-dialog" data-zylora-lead-dialog aria-labelledby="zylora-lead-title">
<div class="zylora-lead-card">
<button type="button" class="zylora-lead-close" data-zylora-lead-close aria-label="Close enquiry form">Close</button>
<div class="zylora-lead-copy"><p class="zylora-lead-eyebrow">Contact the business</p><h2 id="zylora-lead-title">{heading}</h2><p>{body}</p></div>
<form class="zylora-lead-form" data-zylora-lead-form>
<label>{name_label}<input name="name" autocomplete="name" maxlength="160" required></label>
{email}{phone}
<label>{enquiry_label}<textarea name="enquiry" maxlength="10000" rows="4" required></textarea></label>
<label class="zylora-lead-consent"><input name="contact_consent" type="checkbox" required> <span>{consent}</span></label>
<input name="turnstile_token" type="hidden">{challenge}
<p class="zylora-lead-status" data-zylora-lead-status role="status"></p>
<button type="submit">{submit}</button>
</form>
<div class="zylora-lead-success" data-zylora-lead-success tabindex="-1" hidden>
<h3>Thank you</h3><p>Your enquiry has been sent.</p>
<button type="button" data-zylora-lead-close>Close</button>
</div>
</div>
</dialog>
</div>"""


def _visitor_styles() -> str:
    return """<style>
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;margin:0;color:#17201e}nav,main{max-width:72rem;margin:auto;padding:1.25rem}nav{display:flex;gap:1rem;flex-wrap:wrap}section{padding:2rem 0}h1,h2{line-height:1.1}button,input,textarea{font:inherit}button{cursor:pointer}.zylora-lead-inline button,.zylora-chatbot button,.zylora-lead-card button{border:0;border-radius:.75rem;background:#173f35;color:#fff;padding:.72rem 1rem;font-weight:700}.zylora-chatbot{position:fixed;right:1rem;bottom:1rem;max-width:min(24rem,calc(100vw - 2rem));z-index:10}.zylora-chatbot__panel{margin-top:.5rem;padding:1rem;border:1px solid #d6ded9;border-radius:1rem;background:#fff;box-shadow:0 1rem 3rem #17201e33}.zylora-chatbot__messages{display:grid;gap:.5rem;max-height:16rem;overflow:auto}.zylora-chatbot__message{margin:0;padding:.55rem .7rem;border-radius:.65rem;background:#f1f5f2}.zylora-chatbot__message--visitor{background:#dbece1}.zylora-chatbot__form{display:grid;gap:.5rem;margin-top:.75rem}.zylora-chatbot__form input{display:block;width:100%;margin-top:.25rem;padding:.65rem;border:1px solid #9eaaa5;border-radius:.55rem}.zylora-chatbot__enquiry{margin-top:.75rem;background:#fff!important;color:#173f35!important;border:1px solid #9eaaa5!important}.zylora-lead-dialog{width:min(42rem,calc(100vw - 2rem));max-height:calc(100dvh - 2rem);padding:0;border:0;border-radius:1.25rem;background:transparent;color:#17201e;overflow:auto}.zylora-lead-dialog::backdrop{background:#0d1c18a8;backdrop-filter:blur(4px)}.zylora-lead-dialog[open]{animation:zylora-lead-enter .28s ease-out}.zylora-lead-card{position:relative;padding:clamp(1.25rem,4vw,2.25rem);border:1px solid #d6ded9;border-radius:1.25rem;background:#fff;box-shadow:0 1.5rem 5rem #0d1c1852}.zylora-lead-close{position:absolute;right:1rem;top:1rem;background:#eef3f0!important;color:#173f35!important}.zylora-lead-copy{padding-right:4.5rem}.zylora-lead-copy h2{margin:.25rem 0 .5rem;font-size:clamp(1.7rem,5vw,2.5rem)}.zylora-lead-eyebrow{margin:0;color:#396c5e;font-size:.78rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.zylora-lead-form{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1.4rem}.zylora-lead-form label{display:grid;gap:.35rem;font-weight:650}.zylora-lead-form label:has(textarea),.zylora-lead-consent,.zylora-lead-status,.cf-turnstile,.zylora-lead-form>button{grid-column:1/-1}.zylora-lead-form input:not([type=checkbox]),.zylora-lead-form textarea{width:100%;padding:.72rem;border:1px solid #9eaaa5;border-radius:.6rem;background:#fff;color:#17201e}.zylora-lead-consent{grid-template-columns:auto 1fr!important;align-items:start;font-weight:500!important}.zylora-lead-status{min-height:1.4rem;margin:0;color:#8c2f22}.zylora-lead-success{padding:3rem 0 1rem;text-align:center}.zylora-lead-success h3{font-size:2rem;margin:0}.zylora-lead-success[hidden],[hidden]{display:none!important}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #d8864d;outline-offset:2px}@keyframes zylora-lead-enter{from{opacity:0;transform:translateY(1rem) scale(.98)}to{opacity:1;transform:none}}@media(max-width:40rem){.zylora-lead-form{grid-template-columns:1fr}.zylora-lead-dialog{width:calc(100vw - 1rem);max-height:calc(100dvh - 1rem)}.zylora-chatbot{right:.5rem;bottom:.5rem;max-width:calc(100vw - 1rem)}}@media(prefers-reduced-motion:reduce){.zylora-lead-dialog[open]{animation:none}}
</style>"""


def _analytics_widget() -> str:
    """Platform-authored anonymous session instrumentation for the host-resolved public API."""

    return """<script>(()=>{const key='zylora.analytics.session';const create=()=>globalThis.crypto?.randomUUID?.().replaceAll('-','')||Math.random().toString(36).slice(2).padEnd(16,'0');let session;try{session=sessionStorage.getItem(key)||create();sessionStorage.setItem(key,session);}catch{session=create();}const event=create();fetch('/api/v1/public/analytics/page-views',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:event,session_id:session,page_path:location.pathname||'/'})}).catch(()=>{});})();</script>"""


def render_page(
    page: dict[str, Any],
    navigation: list[tuple[str, str]],
    *,
    include_chatbot: bool = True,
    include_analytics: bool = True,
    lead_form: dict[str, Any] | None = None,
    turnstile_site_key: str | None = None,
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
    lead_capture = _lead_form_widget(lead_form, turnstile_site_key) if lead_form is not None else ""
    chatbot = _chatbot_widget(lead_form is not None) if include_chatbot else ""
    analytics = _analytics_widget() if include_analytics else ""
    runtime = (
        f"<script>{VISITOR_RUNTIME}</script>" if include_chatbot or lead_form is not None else ""
    )
    turnstile = (
        '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
        if lead_form is not None and turnstile_site_key
        else ""
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_text(seo.get("title")) or name}</title><meta name="description" content="{description}">'
        f"{_visitor_styles()}</head><body><nav>{nav}</nav>"
        f"<main><h1>{name}</h1>{content}</main>{chatbot}{lead_capture}{analytics}"
        f"{runtime}{turnstile}</body></html>"
    ).encode()


class ArtifactBuilder:
    def __init__(self, storage: ObjectStorage, *, turnstile_site_key: str | None = None) -> None:
        self.storage = storage
        self.turnstile_site_key = turnstile_site_key

    def build(
        self, deployment_id: UUID, pages: list[dict[str, Any]], redirects: dict[str, str]
    ) -> BuiltArtifact:
        navigation = [
            (str(page.get("name") or page.get("label") or "Page"), str(page.get("path") or "/"))
            for page in pages
            if page.get("show_in_navigation") is True
        ]
        lead_form = _find_lead_form(pages)
        files: dict[str, str] = {}
        prefix = f"deployments/{deployment_id}"
        for page in pages:
            path = str(page.get("path") or "/")
            key_path = "index.html" if path == "/" else f"{path.strip('/')}/index.html"
            key = f"{prefix}/{key_path}"
            data = render_page(
                page,
                navigation,
                include_chatbot=True,
                lead_form=lead_form,
                turnstile_site_key=self.turnstile_site_key,
            )
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
