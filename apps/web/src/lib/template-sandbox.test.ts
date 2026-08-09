import { describe, expect, it } from 'vitest';

import type { TemplateDocument } from '@zylora/template-schema';
import { sandboxDocument } from './template-sandbox';

const document: TemplateDocument = {
  schema_version: '1.0.0',
  registry_version: '1.0.0',
  metadata: { name: 'Safe', description: 'Safe preview', language: 'en' },
  theme: {
    primary: '#164E46',
    accent: '#E37A5F',
    surface: '#FFFDF8',
    ink: '#17211D',
    heading_font: 'MANROPE',
    body_font: 'INTER',
  },
  assets: [],
  pages: [
    {
      id: 'home-page',
      slug: 'home',
      label: 'Home',
      parent_page_id: null,
      sort_order: 0,
      is_home: true,
      show_in_navigation: true,
      status: 'ACTIVE',
      seo: { title: 'Safe', description: 'Safe preview' },
      components: [
        {
          id: 'hero',
          type: 'HERO',
          props: { heading: 'Safe <script>alert(1)</script>', body: 'A useful preview' },
          children: [],
          responsive: {},
          interactions: [],
        },
      ],
    },
  ],
  features: [],
  requirements: [],
  provenance: 'CURATED',
};

describe('sandboxDocument', () => {
  it('escapes content and denies network, scripts, forms, and base URLs', () => {
    const html = sandboxDocument(document);
    expect(html).toContain("default-src 'none'");
    expect(html).toContain("form-action 'none'");
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });
});
