import { describe, expect, it } from 'vitest';

import RootLayout, { metadata } from './layout';

describe('RootLayout', () => {
  it('sets the document language and fails closed until production indexing is explicitly enabled', () => {
    const layout = RootLayout({ children: <p>Identity content</p> });

    expect(layout.props.lang).toBe('en');
    const bodyChildren = layout.props.children.props.children;
    expect(bodyChildren).toHaveLength(2);
    expect(bodyChildren[1].props.children.props.children).toBe('Identity content');
    expect(metadata.robots).toMatchObject({ index: false, follow: false, nocache: true });
  });
});
