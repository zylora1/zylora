import type { CSSProperties, ReactNode } from 'react';

export type TemplateLink = {
  kind: 'PAGE' | 'SECTION' | 'EXTERNAL' | 'EMAIL' | 'PHONE';
  target: string;
};

export type TemplateComponent = {
  id: string;
  type: string;
  props: Record<string, unknown>;
  children: TemplateComponent[];
  responsive: Record<string, Record<string, unknown>>;
  interactions: Array<{ trigger: string; action: string; target?: string }>;
};

export type TemplateDocument = {
  schema_version: '1.0.0';
  registry_version: '1.0.0';
  metadata: { name: string; description: string; language: string };
  theme: {
    primary: string;
    accent: string;
    surface: string;
    ink: string;
    heading_font: string;
    body_font: string;
  };
  assets: Array<{ id: string; alt: string }>;
  pages: Array<{
    id: string;
    slug: string;
    label: string;
    parent_page_id: string | null;
    sort_order: number;
    is_home: boolean;
    show_in_navigation: boolean;
    status: 'ACTIVE' | 'HIDDEN';
    seo: { title: string; description: string };
    components: TemplateComponent[];
  }>;
  features: string[];
  requirements: string[];
  provenance: 'CURATED' | 'LICENSED' | 'CUSTOM';
};

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function linkHref(value: unknown): string {
  if (!value || typeof value !== 'object') return '#';
  const link = value as Partial<TemplateLink>;
  if (link.kind === 'PAGE') return link.target === 'home' ? '/' : `/${link.target ?? ''}`;
  if (link.kind === 'SECTION') return `#${link.target ?? ''}`;
  if (link.kind === 'EMAIL') return `mailto:${link.target ?? ''}`;
  if (link.kind === 'PHONE') return `tel:${link.target ?? ''}`;
  return typeof link.target === 'string' && link.target.startsWith('https://') ? link.target : '#';
}

function itemList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object',
      )
    : [];
}

function RenderComponent({ component }: { component: TemplateComponent }): ReactNode {
  const p = component.props;
  const children = component.children.map((child) => (
    <RenderComponent key={child.id} component={child} />
  ));
  switch (component.type) {
    case 'NAVIGATION':
      return (
        <nav className="zt-nav" aria-label="Primary">
          <strong>{text(p.brand)}</strong>
          <div>
            {itemList(p.links).map((link) => (
              <a key={text(link.label)} href={linkHref(link.link)}>
                {text(link.label)}
              </a>
            ))}
          </div>
        </nav>
      );
    case 'HERO':
      return (
        <section id={component.id} className={`zt-hero zt-hero--${text(p.align) || 'left'}`}>
          <p className="zt-eyebrow">{text(p.eyebrow)}</p>
          <h1>{text(p.heading)}</h1>
          <p>{text(p.body)}</p>
          <div className="zt-actions">
            {p.primaryCta ? (
              <a href={linkHref((p.primaryCta as Record<string, unknown>).link)}>
                {text((p.primaryCta as Record<string, unknown>).label)}
              </a>
            ) : null}
            {p.secondaryCta ? (
              <a
                className="zt-secondary"
                href={linkHref((p.secondaryCta as Record<string, unknown>).link)}
              >
                {text((p.secondaryCta as Record<string, unknown>).label)}
              </a>
            ) : null}
          </div>
        </section>
      );
    case 'SECTION':
      return (
        <section id={component.id} className={`zt-section zt-tone--${text(p.tone)}`}>
          <p className="zt-eyebrow">{text(p.eyebrow)}</p>
          {p.heading ? <h2>{text(p.heading)}</h2> : null}
          {p.body ? <p>{text(p.body)}</p> : null}
          {children}
        </section>
      );
    case 'HEADING': {
      const level = Number(p.level);
      return level === 1 ? (
        <h1>{text(p.text)}</h1>
      ) : level === 3 ? (
        <h3>{text(p.text)}</h3>
      ) : (
        <h2>{text(p.text)}</h2>
      );
    }
    case 'RICH_TEXT':
      return <p className="zt-rich-text">{text(p.text)}</p>;
    case 'GRID':
      return (
        <div
          className="zt-grid"
          style={{ '--zt-columns': Number(p.columns) || 3 } as CSSProperties}
        >
          {children}
        </div>
      );
    case 'CARD':
      return (
        <article className="zt-card">
          <p className="zt-eyebrow">{text(p.eyebrow)}</p>
          <h3>{text(p.heading)}</h3>
          <p>{text(p.body)}</p>
          {p.link ? <a href={linkHref(p.link)}>Learn more</a> : null}
          {children}
        </article>
      );
    case 'SERVICES':
      return (
        <section className="zt-list">
          <h2>{text(p.heading)}</h2>
          <div className="zt-grid">
            {itemList(p.items).map((item) => (
              <article className="zt-card" key={text(item.heading)}>
                <h3>{text(item.heading)}</h3>
                <p>{text(item.body)}</p>
              </article>
            ))}
          </div>
        </section>
      );
    case 'TESTIMONIALS':
      return (
        <section className="zt-quotes">
          <h2>{text(p.heading)}</h2>
          {itemList(p.items).map((item) => (
            <blockquote key={text(item.quote)}>
              <p>“{text(item.quote)}”</p>
              <cite>{text(item.name)}</cite>
            </blockquote>
          ))}
        </section>
      );
    case 'FAQ':
      return (
        <section className="zt-faq">
          <h2>{text(p.heading)}</h2>
          {itemList(p.items).map((item) => (
            <details key={text(item.question)}>
              <summary>{text(item.question)}</summary>
              <p>{text(item.answer)}</p>
            </details>
          ))}
        </section>
      );
    case 'LEAD_FORM':
      return (
        <section className="zt-form">
          <h2>{text(p.heading)}</h2>
          <p>{text(p.body)}</p>
          {itemList(p.fields).map((field) => (
            <label key={text(field.name)}>
              {text(field.label)}
              <input name={text(field.name)} type={text(field.type) || 'text'} />
            </label>
          ))}
          <label className="zt-consent">
            <input type="checkbox" /> {text(p.consentText)}
          </label>
          <button type="button">{text(p.submitLabel)}</button>
        </section>
      );
    case 'CONTACT':
      return (
        <address className="zt-contact">
          <h2>{text(p.heading)}</h2>
          {p.email ? <a href={`mailto:${text(p.email)}`}>{text(p.email)}</a> : null}
          {p.phone ? <a href={`tel:${text(p.phone)}`}>{text(p.phone)}</a> : null}
          <p>{text(p.address)}</p>
        </address>
      );
    case 'FOOTER':
      return (
        <footer className="zt-footer">
          <strong>{text(p.brand)}</strong>
          <p>{text(p.body)}</p>
        </footer>
      );
    case 'CHATBOT_MOUNT':
      return (
        <button type="button" className="zt-chatbot" aria-label={text(p.label) || 'Open chat'}>
          Chat
        </button>
      );
    default:
      return null;
  }
}

export function TemplateRenderer({
  document,
  page = 'home',
}: {
  document: TemplateDocument;
  page?: string;
}) {
  const selected = document.pages.find((item) => item.slug === page) ?? document.pages[0];
  const style = {
    '--zt-primary': document.theme.primary,
    '--zt-accent': document.theme.accent,
    '--zt-surface': document.theme.surface,
    '--zt-ink': document.theme.ink,
  } as CSSProperties;
  return (
    <div className="zt-site" style={style} lang={document.metadata.language}>
      {selected?.components.map((component) => (
        <RenderComponent key={component.id} component={component} />
      ))}
    </div>
  );
}
