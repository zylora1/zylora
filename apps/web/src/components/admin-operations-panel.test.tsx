import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AdminOverviewPanel, AdminSectionPanel } from './admin-operations-panel';

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'zylora_admin_csrf=; Max-Age=0';
});

describe('Phase 12 Super Admin operations panels', () => {
  it('renders measured platform state without synthetic values', async () => {
    document.cookie = 'zylora_admin_csrf=admin-test';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          generated_at: '2026-08-10T00:00:00Z',
          metrics: [
            { key: 'users', label: 'Users', value: 2 },
            { key: 'websites', label: 'Websites', value: 3 },
          ],
          analytics_window_start: '2026-07-12',
          page_views_last_30_days: 9,
          leads_last_30_days: 1,
        }),
      }),
    );

    render(<AdminOverviewPanel />);

    expect(await screen.findByRole('heading', { name: 'Authoritative operations' })).toBeVisible();
    expect(screen.getByText('No synthetic metrics')).toBeVisible();
    expect(screen.getByText('Users')).toBeVisible();
    expect(screen.getByText(/Last 30 measured days since/)).toHaveTextContent(
      '9 page views and 1 Leads.',
    );
  });

  it('renders platform records through the operational API instead of placeholders', async () => {
    document.cookie = 'zylora_admin_csrf=admin-test';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          section: 'audit',
          items: [
            {
              id: 'audit-1',
              label: 'template.publish',
              detail: 'admin@example.com',
              status: null,
              occurred_at: '2026-08-10T00:00:00Z',
              attributes: { correlation_id: 'correlation-1' },
            },
          ],
        }),
      }),
    );

    render(
      <AdminSectionPanel
        section={{
          slug: 'audit',
          label: 'Audit',
          description: 'Immutable evidence.',
          emptyTitle: 'Unused',
          emptyDescription: 'Unused',
        }}
      />,
    );

    expect(await screen.findByText('template.publish')).toBeVisible();
    expect(screen.getByText('correlation id: correlation-1')).toBeVisible();
    expect(screen.queryByText('No audit query has run')).not.toBeInTheDocument();
  });
});
