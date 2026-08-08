import { describe, expect, it } from 'vitest';

import RootLayout, { metadata } from './layout';

describe('RootLayout', () => {
  it('sets the document language and keeps the foundation out of search indexes', () => {
    const layout = RootLayout({ children: <p>Foundation content</p> });

    expect(layout.props.lang).toBe('en');
    expect(layout.props.children.props.children.props.children).toBe('Foundation content');
    expect(metadata.robots).toMatchObject({ index: false, follow: false });
  });
});
