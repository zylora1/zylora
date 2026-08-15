import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AdminOverviewPanel, AdminSectionPanel } from './admin-operations-panel';

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'zylora_admin_csrf=; Max-Age=0';
});

describe('Super Admin operations panels', () => {
  it('renders the North Star and persisted product funnel', async () => {
    document.cookie = 'zylora_admin_csrf=admin-test';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((input: RequestInfo | URL) => {
        const url = String(input);
        const payload = url.includes('/analytics/growth')
          ? {
              range_days: 30,
              funnel: [
                {
                  key: 'ACCOUNT_CREATED',
                  label: 'Accounts created',
                  count: 10,
                  conversion_percent: 100,
                },
                {
                  key: 'FIRST_LEAD',
                  label: 'Received first lead',
                  count: 3,
                  conversion_percent: 30,
                },
              ],
              active_value_sites_30d: 3,
              previous_active_value_sites_30d: 2,
              active_value_sites_change_percent: 50,
              retention: [],
              published_with_first_lead: 3,
              published_with_zero_leads: 4,
              paid_with_first_lead: 2,
              paid_with_zero_leads: 1,
              subscription_state_counts: { ACTIVE: 3, CANCELLED: 1 },
            }
          : {
              generated_at: '2026-08-10T00:00:00Z',
              metrics: [
                { key: 'users', label: 'Users', value: 2 },
                { key: 'websites', label: 'Websites', value: 3 },
              ],
              analytics_window_start: '2026-07-12',
              page_views_last_30_days: 9,
              leads_last_30_days: 1,
            };
        return Promise.resolve({ ok: true, status: 200, json: async () => payload });
      }),
    );

    render(<AdminOverviewPanel />);
    expect(await screen.findByRole('heading', { name: 'Authoritative operations' })).toBeVisible();
    expect(
      screen.getByRole('heading', { name: /Published Websites delivering real enquiries/i }),
    ).toBeVisible();
    expect(screen.getByText('+50% vs prior 30 days')).toBeVisible();
    expect(screen.getByText('Received first lead')).toBeVisible();
    expect(screen.getByText('Published + first lead')).toBeVisible();
    expect(screen.getByText(/3 active.*1 cancelled/)).toBeVisible();
    expect(screen.getByText('No synthetic metrics')).toBeVisible();
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
  });
});
