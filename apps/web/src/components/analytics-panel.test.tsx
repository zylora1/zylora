import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AnalyticsPanel } from './analytics-panel';

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'zylora_user_csrf=; Max-Age=0';
});

describe('Phase 11 Analytics panel', () => {
  it('uses the required first-publish CTA without inventing metrics', async () => {
    document.cookie = 'zylora_user_csrf=analytics-test';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          has_published_website: false,
          has_meaningful_data: false,
          page_views: 0,
          sessions: 0,
          visitors: 0,
          leads: 0,
          form_leads: 0,
          chatbot_leads: 0,
          chatbot_conversations: 0,
          chatbot_messages: 0,
          conversions: 0,
          points: [],
        }),
      }),
    );
    render(<AnalyticsPanel />);

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Publish your first website' }),
    ).toBeVisible();
    expect(screen.getByRole('link', { name: 'Choose a Template' })).toHaveAttribute(
      'href',
      '/app/templates',
    );
    expect(screen.queryByText('Page views')).not.toBeInTheDocument();
  });

  it('renders only measured rollup metrics and recorded days', async () => {
    document.cookie = 'zylora_user_csrf=analytics-test';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          has_published_website: true,
          has_meaningful_data: true,
          page_views: 12,
          sessions: 8,
          visitors: 5,
          leads: 2,
          form_leads: 1,
          chatbot_leads: 1,
          chatbot_conversations: 3,
          chatbot_messages: 7,
          conversions: 2,
          points: [
            {
              date: '2026-08-10',
              page_views: 12,
              sessions: 8,
              visitors: 5,
              leads: 2,
              form_leads: 1,
              chatbot_leads: 1,
              chatbot_conversations: 3,
              chatbot_messages: 7,
              conversions: 2,
            },
          ],
        }),
      }),
    );
    render(<AnalyticsPanel />);

    expect(await screen.findByRole('heading', { name: 'Measured Website activity' })).toBeVisible();
    expect(screen.getByText('Verified rollups')).toBeVisible();
    expect(screen.getAllByText('12')).toHaveLength(2);
    expect(screen.getByRole('columnheader', { name: 'Chatbot' })).toBeVisible();
    expect(screen.getByRole('cell', { name: '3' })).toBeVisible();
  });

  it('does not render synthetic totals before a published Website gets activity', async () => {
    document.cookie = 'zylora_user_csrf=analytics-test';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          has_published_website: true,
          has_meaningful_data: false,
          points: [],
        }),
      }),
    );
    render(<AnalyticsPanel />);

    expect(await screen.findByText(/Zylora does not invent charts/i)).toBeVisible();
    expect(screen.queryByText('Verified rollups')).not.toBeInTheDocument();
  });
});
