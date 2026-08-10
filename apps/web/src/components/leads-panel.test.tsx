import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { LeadsPanel } from './leads-panel';

afterEach(() => vi.unstubAllGlobals());

describe('Phase 10 Leads panel', () => {
  it('shows server-backed credits and switches between Website-scoped Leads', async () => {
    const fetcher = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/websites') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            items: [
              { id: 'site-a', display_name: 'Dental A', status: 'PUBLISHED' },
              { id: 'site-b', display_name: 'Bakery B', status: 'DRAFT' },
            ],
          }),
        });
      }
      if (path === '/api/v1/lead-credits') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ balance: -1, policy: 'ALLOW_DEBT' }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () =>
          path.includes('site-a')
            ? [
                {
                  id: 'lead-a',
                  source: 'FORM',
                  name: 'Ada Visitor',
                  email: 'ada@example.com',
                  phone: null,
                  enquiry: 'Please call me.',
                  page_path: '/contact',
                  status: 'NEW',
                  captured_at: '2026-08-10T09:00:00Z',
                },
              ]
            : [],
      });
    });
    vi.stubGlobal('fetch', fetcher);
    render(<LeadsPanel />);

    expect(await screen.findByText('Ada Visitor')).toBeVisible();
    expect(screen.getByText('Current ledger balance')).toBeVisible();
    fireEvent.change(screen.getByLabelText('Website'), { target: { value: 'site-b' } });
    expect(await screen.findByText(/no captured leads yet/i)).toBeVisible();
    await waitFor(() =>
      expect(fetcher).toHaveBeenCalledWith(
        '/api/v1/websites/site-b/leads?limit=50',
        expect.any(Object),
      ),
    );
  });
});
