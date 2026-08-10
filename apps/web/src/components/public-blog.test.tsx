import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { BlogArticle, BlogIndex } from './public-blog';

const posts = [
  {
    title: 'Publishing with confidence',
    slug: 'publishing-confidence',
    excerpt: 'A considered publishing workflow.',
    published_at: '2026-08-18T10:00:00Z',
    categories: ['Product'],
    tags: ['publish'],
  },
  {
    title: 'A related note',
    slug: 'related-note',
    excerpt: 'A second article.',
    published_at: '2026-08-17T10:00:00Z',
    categories: ['Product'],
    tags: ['notes'],
  },
];

afterEach(() => vi.unstubAllGlobals());

describe('public Blog', () => {
  it('renders only published Blog data from the public API', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => posts,
    });
    vi.stubGlobal('fetch', fetcher);

    render(<BlogIndex />);

    expect(
      await screen.findByRole('heading', { name: 'Publishing with confidence' }),
    ).toBeVisible();
    expect(fetcher).toHaveBeenCalledWith(
      '/api/v1/blog/posts',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('renders safe API content with breadcrumb, related links, and Article JSON-LD', async () => {
    const fetcher = vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () =>
          url.includes('publishing-confidence')
            ? {
                ...posts[0],
                content_html: '<h2>Plan the transition</h2><p>Use a revision.</p>',
                featured_image_url: null,
                seo_title: 'Publishing title',
                meta_description: 'Publishing description',
                canonical_path: '/blog/publishing-confidence',
                og_title: null,
                og_description: null,
              }
            : posts,
      }),
    );
    vi.stubGlobal('fetch', fetcher);

    const { container } = render(<BlogArticle slug="publishing-confidence" />);

    expect(
      await screen.findByRole('heading', { name: 'Publishing with confidence' }),
    ).toBeVisible();
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Journal');
    expect(screen.getByRole('link', { name: 'A related note' })).toHaveAttribute(
      'href',
      '/blog/related-note',
    );
    expect(container.querySelector('script[type="application/ld+json"]')).toHaveTextContent(
      'Publishing title',
    );
  });
});
