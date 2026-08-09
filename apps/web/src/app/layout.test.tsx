import { describe, expect, it } from 'vitest';

import RootLayout, { metadata } from './layout';

describe('RootLayout', () => {
  it('sets the document language and keeps the public root indexable while private layouts own noindex', () => {
    const layout = RootLayout({ children: <p>Identity content</p> });

    expect(layout.props.lang).toBe('en');
    expect(layout.props.children.props.children.props.children).toBe('Identity content');
    expect(metadata.robots).toMatchObject({ index: true, follow: true });
  });
});
