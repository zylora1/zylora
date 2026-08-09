import type { TemplateComponent, TemplateDocument } from '@zylora/template-schema';

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}
function escapeHtml(value: unknown): string {
  return text(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
function items(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object',
      )
    : [];
}

function componentHtml(component: TemplateComponent): string {
  const p = component.props;
  const children = component.children.map(componentHtml).join('');
  if (component.type === 'NAVIGATION') return `<nav><strong>${escapeHtml(p.brand)}</strong></nav>`;
  if (component.type === 'HERO')
    return `<section class="hero"><small>${escapeHtml(p.eyebrow)}</small><h1>${escapeHtml(p.heading)}</h1><p>${escapeHtml(p.body)}</p></section>`;
  if (component.type === 'SERVICES')
    return `<section><h2>${escapeHtml(p.heading)}</h2><div class="grid">${items(p.items)
      .map(
        (item) =>
          `<article><h3>${escapeHtml(item.heading)}</h3><p>${escapeHtml(item.body)}</p></article>`,
      )
      .join('')}</div></section>`;
  if (component.type === 'TESTIMONIALS')
    return `<section class="soft"><h2>${escapeHtml(p.heading)}</h2>${items(p.items)
      .map(
        (item) =>
          `<blockquote>“${escapeHtml(item.quote)}”<cite>${escapeHtml(item.name)}</cite></blockquote>`,
      )
      .join('')}</section>`;
  if (component.type === 'FAQ')
    return `<section><h2>${escapeHtml(p.heading)}</h2>${items(p.items)
      .map(
        (item) =>
          `<details><summary>${escapeHtml(item.question)}</summary><p>${escapeHtml(item.answer)}</p></details>`,
      )
      .join('')}</section>`;
  if (component.type === 'LEAD_FORM')
    return `<section class="form"><h2>${escapeHtml(p.heading)}</h2><p>${escapeHtml(p.body)}</p>${items(
      p.fields,
    )
      .map((field) => `<label>${escapeHtml(field.label)}<input disabled></label>`)
      .join('')}<button disabled>${escapeHtml(p.submitLabel)}</button></section>`;
  if (component.type === 'FOOTER')
    return `<footer><strong>${escapeHtml(p.brand)}</strong><p>${escapeHtml(p.body)}</p></footer>`;
  if (component.type === 'SECTION')
    return `<section><small>${escapeHtml(p.eyebrow)}</small><h2>${escapeHtml(p.heading)}</h2><p>${escapeHtml(p.body)}</p>${children}</section>`;
  if (component.type === 'GRID') return `<div class="grid">${children}</div>`;
  if (component.type === 'CARD')
    return `<article><h3>${escapeHtml(p.heading)}</h3><p>${escapeHtml(p.body)}</p>${children}</article>`;
  if (component.type === 'HEADING') return `<h2>${escapeHtml(p.text)}</h2>`;
  if (component.type === 'RICH_TEXT') return `<p>${escapeHtml(p.text)}</p>`;
  return '';
}

export function sandboxDocument(document: TemplateDocument, page = 'home'): string {
  const selected = document.pages.find((item) => item.slug === page) ?? document.pages[0];
  const t = document.theme;
  const body = selected?.components.map(componentHtml).join('') ?? '';
  return `<!doctype html><html lang="${escapeHtml(document.metadata.language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'"><style>*{box-sizing:border-box}body{margin:0;background:${t.surface};color:${t.ink};font:16px/1.6 Arial,sans-serif}nav{padding:20px clamp(20px,7vw,80px);border-bottom:1px solid #bbb}.hero{min-height:540px;display:grid;align-content:center;padding:clamp(60px,10vw,120px) clamp(20px,8vw,110px);background:${t.primary};color:white}.hero h1{max-width:11ch;margin:8px 0 20px;font:600 clamp(48px,8vw,104px)/.92 Georgia,serif;letter-spacing:-.055em}.hero small,section>small{color:${t.accent};font-weight:900;letter-spacing:.14em}section{padding:clamp(55px,8vw,105px) clamp(20px,8vw,110px)}section h2{font:600 clamp(32px,5vw,64px)/1 Georgia,serif}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.grid article{border-top:3px solid ${t.accent};background:#fff;padding:24px}.soft{background:#f1f3ef}blockquote{max-width:850px;margin:32px 0;font:500 clamp(26px,4vw,54px)/1.18 Georgia,serif}cite{display:block;margin-top:16px;font:700 14px Arial}.form{background:${t.primary};color:white}.form label{display:grid;max-width:600px;margin:14px 0}.form input{height:44px}.form button{padding:13px 18px;background:${t.accent}}details{max-width:800px;border-bottom:1px solid #aaa;padding:16px 0}footer{padding:48px clamp(20px,8vw,110px);background:#17211d;color:white}@media(max-width:700px){.grid{grid-template-columns:1fr}.hero{min-height:470px}}</style></head><body>${body}</body></html>`;
}
