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
function linkTarget(value: unknown): string {
  if (!value || typeof value !== 'object') return '#';
  const link = value as Record<string, unknown>;
  if (link.kind === 'SECTION') return `#${escapeHtml(link.target)}`;
  if (link.kind === 'PAGE') return link.target === 'home' ? '/' : `/${escapeHtml(link.target)}`;
  if (link.kind === 'EMAIL') return `mailto:${escapeHtml(link.target)}`;
  if (link.kind === 'PHONE') return `tel:${escapeHtml(link.target)}`;
  return '#';
}

function componentHtml(component: TemplateComponent): string {
  const p = component.props;
  const children = component.children.map(componentHtml).join('');
  if (component.type === 'NAVIGATION')
    return `<nav><strong>${escapeHtml(p.brand)}</strong><div>${items(p.links)
      .map((link) => `<a href="${linkTarget(link.link)}">${escapeHtml(link.label)}</a>`)
      .join('')}</div></nav>`;
  if (component.type === 'HERO') {
    const align = text(p.align) === 'center' ? ' center' : '';
    const treatment = ['studio', 'journal', 'signal', 'atelier', 'compact'].includes(
      text(p.treatment),
    )
      ? text(p.treatment)
      : 'studio';
    const primary = p.primaryCta as Record<string, unknown> | undefined;
    const secondary = p.secondaryCta as Record<string, unknown> | undefined;
    return `<section class="hero${align} treatment-${escapeHtml(treatment)}"><small>${escapeHtml(p.eyebrow)}</small><h1>${escapeHtml(p.heading)}</h1><p>${escapeHtml(p.body)}</p><div class="actions">${primary ? `<a href="${linkTarget(primary.link)}">${escapeHtml(primary.label)}</a>` : ''}${secondary ? `<a class="secondary" href="${linkTarget(secondary.link)}">${escapeHtml(secondary.label)}</a>` : ''}</div></section>`;
  }
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
  if (component.type === 'MEDIA') {
    const mode = ['split', 'gallery', 'band', 'portrait'].includes(text(p.mode))
      ? text(p.mode)
      : 'split';
    const panels = mode === 'gallery' ? 3 : mode === 'band' ? 2 : 1;
    return `<section class="media native ${escapeHtml(mode)}"><div class="media-copy"><h2>${escapeHtml(p.heading)}</h2><p>${escapeHtml(p.body)}</p></div><div class="media-grid" style="--media-columns:${panels}" role="img" aria-label="${escapeHtml(p.body || p.heading)}">${Array.from({ length: panels }, (_, index) => `<span class="media-art" data-index="${index}" aria-hidden="true"></span>`).join('')}</div></section>`;
  }
  if (component.type === 'IMAGE')
    return `<figure class="media image"><div class="media-art" role="img" aria-label="${escapeHtml(p.caption || 'Template media')}"></div>${p.caption ? `<figcaption>${escapeHtml(p.caption)}</figcaption>` : ''}</figure>`;
  if (component.type === 'GALLERY')
    return `<section class="media gallery"><h2>${escapeHtml(p.heading)}</h2><div class="media-grid" style="--media-columns:${Number(p.columns) || 3}">${Array.isArray(p.assetIds) ? p.assetIds.map((_, index) => `<div class="media-art" data-index="${index}" role="img" aria-label="Template media ${index + 1}"></div>`).join('') : ''}</div></section>`;
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
    return `<section class="tone-${escapeHtml(p.tone)}"><small>${escapeHtml(p.eyebrow)}</small><h2>${escapeHtml(p.heading)}</h2><p>${escapeHtml(p.body)}</p>${children}</section>`;
  if (component.type === 'GRID')
    return `<div class="grid" style="--columns:${Number(p.columns) || 3}">${children}</div>`;
  if (component.type === 'CARD')
    return `<article><small>${escapeHtml(p.eyebrow)}</small><h3>${escapeHtml(p.heading)}</h3><p>${escapeHtml(p.body)}</p>${children}</article>`;
  if (component.type === 'HEADING') return `<h2>${escapeHtml(p.text)}</h2>`;
  if (component.type === 'RICH_TEXT') return `<p>${escapeHtml(p.text)}</p>`;
  return '';
}

export function sandboxDocument(document: TemplateDocument, page = 'home'): string {
  const selected = document.pages.find((item) => item.slug === page) ?? document.pages[0];
  const t = document.theme;
  const body = selected?.components.map(componentHtml).join('') ?? '';
  return `<!doctype html><html lang="${escapeHtml(document.metadata.language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'"><style>*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:${t.surface};color:${t.ink};font:16px/1.6 Arial,sans-serif}nav{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:20px clamp(20px,7vw,80px);border-bottom:1px solid color-mix(in srgb,${t.ink} 20%,transparent)}nav div{display:flex;gap:18px}nav a{color:inherit;font-size:13px;text-decoration:none}.hero{position:relative;overflow:hidden;min-height:540px;display:grid;align-content:center;padding:clamp(60px,10vw,120px) clamp(20px,8vw,110px);background:${t.primary};color:white}.hero.center{justify-items:center;text-align:center}.hero>*{position:relative;z-index:1}.hero:after{position:absolute;content:"";pointer-events:none}.hero.treatment-studio:after{top:12%;right:7%;width:clamp(190px,27vw,440px);border:1px solid #ffffff40;border-radius:50%;background:color-mix(in srgb,${t.accent} 14%,transparent);aspect-ratio:1}.hero.treatment-journal h1{max-width:13ch;font-style:italic}.hero.treatment-signal{min-height:450px;border-left:clamp(8px,1.2vw,16px) solid ${t.accent};background:linear-gradient(110deg,${t.primary} 0 68%,color-mix(in srgb,${t.accent} 32%,${t.primary}) 68%)}.hero.treatment-signal h1{max-width:15ch;font-size:clamp(45px,6.5vw,96px)}.hero.treatment-atelier{position:relative;min-height:500px;margin:clamp(10px,2vw,24px);padding-right:clamp(250px,43vw,670px)}.hero.treatment-atelier:after{inset:8% 5% 8% auto;width:min(31%,430px);border:1px solid #ffffff4d;background:linear-gradient(145deg,transparent 48%,#ffffff26 48.5% 51.5%,transparent 52%),color-mix(in srgb,${t.accent} 24%,${t.primary})}.hero.treatment-compact{min-height:400px;border-bottom:5px solid ${t.accent};padding-block:clamp(48px,6vw,80px)}.hero.treatment-compact h1{max-width:12ch;font-size:clamp(42px,6vw,80px)}.hero h1{max-width:11ch;margin:8px 0 20px;font:600 clamp(48px,8vw,104px)/.92 Georgia,serif;letter-spacing:-.055em}.hero p{max-width:650px}.hero small,section>small,article>small{color:${t.accent};font-weight:900;letter-spacing:.14em}.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}.actions a{border-radius:7px;background:${t.accent};color:#101511;padding:12px 16px;font-size:13px;font-weight:800;text-decoration:none}.actions .secondary{border:1px solid #ffffff70;background:transparent;color:white}section{padding:clamp(55px,8vw,105px) clamp(20px,8vw,110px)}section h2{max-width:14ch;font:600 clamp(32px,5vw,64px)/1 Georgia,serif}.media{margin:0;padding:clamp(36px,6vw,80px) clamp(20px,8vw,110px)}.media.native{display:grid;grid-template-columns:minmax(200px,.4fr) minmax(0,1fr);align-items:center;gap:clamp(20px,5vw,70px)}.media.native.band{grid-template-columns:1fr}.media.native.portrait .media-grid{width:min(72%,600px);margin:auto}.media.image{display:grid;grid-template-columns:minmax(0,1fr) minmax(220px,.35fr);align-items:end;gap:20px}.media-art{position:relative;overflow:hidden;min-height:clamp(260px,40vw,560px);background:linear-gradient(135deg,color-mix(in srgb,${t.primary} 88%,#091119),color-mix(in srgb,${t.accent} 62%,white))}.media-art:before{content:"";position:absolute;inset:12% 10% auto auto;width:42%;aspect-ratio:1;border:1px solid #ffffff60;border-radius:50%}.media-art:after{content:"";position:absolute;inset:auto auto 10% 8%;width:55%;height:32%;border:1px solid #ffffff48;background:#ffffff0d}.media-grid{display:grid;grid-template-columns:repeat(var(--media-columns,3),minmax(0,1fr));gap:12px}.media-grid .media-art:nth-child(2){transform:translateY(22px);filter:saturate(.72)}.media-grid .media-art:nth-child(3){filter:hue-rotate(28deg)}figcaption{font-size:13px;color:color-mix(in srgb,${t.ink} 65%,transparent)}.grid{display:grid;grid-template-columns:repeat(var(--columns,3),minmax(0,1fr));gap:16px}.grid article{border-top:3px solid ${t.accent};background:color-mix(in srgb,${t.primary} 6%,white);padding:24px}.soft,.tone-journal{background:color-mix(in srgb,${t.primary} 8%,${t.surface})}.tone-journal{text-align:center}.tone-signal{border-left:clamp(6px,1vw,13px) solid ${t.accent}}.tone-atelier{width:min(92%,1320px);margin:40px auto}.tone-compact{padding-top:48px;padding-bottom:48px}blockquote{max-width:850px;margin:32px 0;font:500 clamp(26px,4vw,54px)/1.18 Georgia,serif}cite{display:block;margin-top:16px;font:700 14px Arial}.form{background:${t.primary};color:white}.form label{display:grid;max-width:600px;margin:14px 0}.form input{height:44px}.form button{padding:13px 18px;background:${t.accent}}details{max-width:800px;border-bottom:1px solid color-mix(in srgb,${t.ink} 35%,transparent);padding:16px 0}footer{padding:48px clamp(20px,8vw,110px);background:color-mix(in srgb,${t.primary} 82%,#080b12);color:white}@media(max-width:700px){nav div{display:none}.grid,.media-grid,.media.native,.media.image{grid-template-columns:1fr}.hero{min-height:470px}.tone-atelier{width:auto;margin:18px}.hero.treatment-atelier{margin:8px;padding-right:20px;padding-bottom:240px}.hero.treatment-atelier:after{inset:auto 20px 20px;width:auto;height:190px}.hero.treatment-studio:after{top:auto;right:-10%;bottom:-14%;opacity:.65}}</style></head><body>${body}</body></html>`;
}
