import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AnalyticsPanel } from './analytics-panel';

const base = {
  has_published_website: true,
  has_meaningful_data: true,
  page_views: 12,
  sessions: 8,
  visitors: 5,
  leads: 2,
  lead_form_opens: 4,
  lead_form_submissions: 2,
  form_leads: 2,
  chatbot_conversations: 3,
  chatbot_messages: 7,
  lead_conversion_rate: 40,
  published_at: '2026-08-01T00:00:00Z',
  first_visitor_at: '2026-08-02T00:00:00Z',
  first_lead_at: '2026-08-03T00:00:00Z',
  time_to_first_lead_seconds: 172800,
  previous_page_views: 8,
  previous_leads: 1,
  page_view_change_percent: 50,
  lead_change_percent: 100,
  zero_lead_recommendations: [],
  points: [
    {
      date: '2026-08-10',
      page_views: 12,
      sessions: 8,
      visitors: 5,
      leads: 2,
      lead_form_opens: 4,
      lead_form_submissions: 2,
      form_leads: 2,
      chatbot_leads: 0,
      chatbot_conversations: 3,
      chatbot_messages: 7,
      conversions: 2,
    },
  ],
};

function respond(payload: object) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => payload,
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'zylora_user_csrf=; Max-Age=0';
});

describe('outcome analytics panel', () => {
  it('uses the required first-publish CTA without inventing metrics', async () => {
    document.cookie = 'zylora_user_csrf=analytics-test';
    respond({ ...base, has_published_website: false, has_meaningful_data: false, points: [] });
    render(<AnalyticsPanel />);
    expect(
      await screen.findByRole('heading', { level: 2, name: 'Publish your first website' }),
    ).toBeVisible();
    expect(screen.getByRole('link', { name: 'Choose a Template' })).toHaveAttribute(
      'href',
      '/app/templates',
    );
    expect(screen.queryByText('Visitors')).not.toBeInTheDocument();
  });

  it('renders measured business outcomes and trend data', async () => {
    document.cookie = 'zylora_user_csrf=analytics-test';
    respond(base);
    render(<AnalyticsPanel />);
    expect(await screen.findByRole('heading', { name: 'Website outcomes' })).toBeVisible();
    expect(screen.getByText('Delivering value')).toBeVisible();
    expect(screen.getByText('Visitor → enquiry')).toBeVisible();
    expect(screen.getByText('40.00%')).toBeVisible();
    expect(screen.getByRole('columnheader', { name: 'Form opens' })).toBeVisible();
    expect(screen.getByRole('cell', { name: '3' })).toBeVisible();
  });

  it('shows deterministic recommendations when traffic exists without a lead', async () => {
    document.cookie = 'zylora_user_csrf=analytics-test';
    respond({
      ...base,
      leads: 0,
      lead_conversion_rate: 0,
      first_lead_at: null,
      zero_lead_recommendations: ['Make the primary enquiry action clear.'],
    });
    render(<AnalyticsPanel />);
    expect(
      await screen.findByRole('heading', { name: /has not received an enquiry/i }),
    ).toBeVisible();
    expect(screen.getByText('Make the primary enquiry action clear.')).toBeVisible();
  });

  it('shows a meaningful no-traffic state instead of empty charts', async () => {
    document.cookie = 'zylora_user_csrf=analytics-test';
    respond({ ...base, has_meaningful_data: false, points: [] });
    render(<AnalyticsPanel />);
    expect(
      await screen.findByRole('heading', { name: 'Your Website is ready for its first visitor' }),
    ).toBeVisible();
    expect(screen.queryByText('Delivering value')).not.toBeInTheDocument();
  });
});
