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
  features: ['LEAD_CAPTURE'],
  version: 1,
  status: 'PUBLISHED',
  featured_order: 10,
};

afterEach(() => vi.unstubAllGlobals());
describe('TemplateGallery', () => {
  it('renders only API catalogue data and submits server-side filters', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [item], next_cursor: null }),
    });
    vi.stubGlobal('fetch', fetcher);
    render(<TemplateGallery />);
    expect(await screen.findByRole('heading', { name: 'Haven Health' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Search Templates'), { target: { value: 'clinic' } });
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'health-wellness' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    expect(String(fetcher.mock.calls.at(1)?.[0])).toContain('query=clinic');
    expect(String(fetcher.mock.calls.at(1)?.[0])).toContain('category=health-wellness');
  });

  it('shows an honest empty state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [], next_cursor: null }),
      }),
    );
    render(<TemplateGallery />);
    expect(
      await screen.findByRole('heading', { name: 'No approved Templates match' }),
    ).toBeInTheDocument();
  });
});
