import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { TemplateGallery } from './template-gallery';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));

const item = {
  id: '00000000-0000-0000-0000-000000000001',
  slug: 'haven-health',
  name: 'Haven Health',
  summary: 'A calm clinic site.',
  category: 'Health & Wellness',
  category_slug: 'health-wellness',
  tags: ['clinic'],
  features: ['LEAD_CAPTURE', 'RESPONSIVE_PREVIEW'],
  version: 1,
  status: 'PUBLISHED',
  featured_order: 10,
};
const secondItem = {
  ...item,
  id: '00000000-0000-0000-0000-000000000002',
  slug: 'atelier-north',
  name: 'Atelier North',
};

function response(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

afterEach(() => vi.unstubAllGlobals());
describe('TemplateGallery', () => {
  it('renders server-side filters with the complete approved category set', async () => {
    const fetcher = vi
      .fn()
      .mockImplementation((url: string) =>
        Promise.resolve(
          url.includes('/categories')
            ? response([{ slug: 'health-wellness', name: 'Health & Wellness' }])
            : response({ items: [item], next_cursor: null }),
        ),
      );
    vi.stubGlobal('fetch', fetcher);
    render(<TemplateGallery />);
    expect(await screen.findByRole('heading', { name: 'Haven Health' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Health & Wellness' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Search Templates'), { target: { value: 'clinic' } });
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'health-wellness' } });
    fireEvent.change(screen.getByLabelText('Feature'), { target: { value: 'LEAD_CAPTURE' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));
    const appliedUrl = String(fetcher.mock.calls.at(2)?.[0]);
    expect(appliedUrl).toContain('query=clinic');
    expect(appliedUrl).toContain('category=health-wellness');
    expect(appliedUrl).toContain('feature=LEAD_CAPTURE');
  });

  it('appends the next cursor page instead of rendering a 1,000-Template catalogue at once', async () => {
    const fetcher = vi
      .fn()
      .mockImplementation((url: string) =>
        Promise.resolve(
          url.includes('/categories')
            ? response([])
            : url.includes('cursor=next-page')
              ? response({ items: [secondItem], next_cursor: null })
              : response({ items: [item], next_cursor: 'next-page' }),
        ),
      );
    vi.stubGlobal('fetch', fetcher);
    render(<TemplateGallery />);
    expect(await screen.findByRole('heading', { name: 'Haven Health' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Load more Templates' }));
    expect(await screen.findByRole('heading', { name: 'Atelier North' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Haven Health' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Load more Templates' })).not.toBeInTheDocument();
  });

  it('shows an honest empty state', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation((url: string) =>
          Promise.resolve(
            url.includes('/categories') ? response([]) : response({ items: [], next_cursor: null }),
          ),
        ),
    );
    render(<TemplateGallery />);
    expect(
      await screen.findByRole('heading', { name: 'No approved Templates match' }),
    ).toBeInTheDocument();
  });
});
