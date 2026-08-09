import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { BillingPanel } from './billing-panel';
import { PricingCatalog } from './pricing-catalog';
import { PublishControls } from './publish-controls';

const plans = ['FREE', 'BASIC', 'GROWTH', 'BUSINESS'].map((code, index) => ({
  id: `00000000-0000-0000-0000-00000000000${index + 1}`,
  code,
  name: code[0] + code.slice(1).toLowerCase(),
  description: `${code} plan`,
  slot: index + 1,
  most_popular: code === 'GROWTH',
  price: { amount_minor: [0, 39900, 99900, 199900][index], currency: 'INR' },
  interval: 'MONTHLY',
  entitlements: {
    max_pages: [1, 5, 20, 'UNLIMITED'][index],
    custom_domain: index > 0,
    remove_branding: index > 0,
    ai_monthly_credits: [15, 100, 500, 1500][index],
    whatsapp_monthly_notifications: [0, 150, 750, 2000][index],
    analytics_tier: 'BASIC',
    seo_tier: 'AUTOMATIC_BASIC',
  },
}));

const catalog = {
  region: 'INDIA',
  country_code: 'IN',
  currency: 'INR',
  interval: 'MONTHLY',
  items: plans,
};

afterEach(() => vi.unstubAllGlobals());

describe('Phase 7 commerce surfaces', () => {
  it('renders the authoritative India monthly catalog and Growth badge', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => catalog }),
    );
    render(<PricingCatalog />);
    expect(await screen.findByText('₹399')).toBeVisible();
    expect(screen.getByText('₹999')).toBeVisible();
    expect(screen.getByText('₹1,999')).toBeVisible();
    expect(screen.getByText('MOST POPULAR')).toBeVisible();
    expect(screen.queryByText(/annual/i)).not.toBeInTheDocument();
    expect(screen.getAllByText('Unlimited Lead capture')).toHaveLength(4);
  });

  it('shows an existing subscription without enabling a placeholder checkout', async () => {
    const fetcher = vi.fn().mockImplementation((path: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () =>
          String(path).endsWith('/plans')
            ? catalog
            : {
                plan_code: 'BUSINESS',
                state: 'ACTIVE',
                is_paid: true,
                price: plans[3]!.price,
                interval: 'MONTHLY',
                current_period_start: '2026-08-01T00:00:00Z',
                current_period_end: '2026-09-01T00:00:00Z',
                cancel_at_period_end: false,
                entitlements: plans[3]!.entitlements,
              },
      }),
    );
    vi.stubGlobal('fetch', fetcher);
    render(<BillingPanel />);
    expect(await screen.findByRole('heading', { name: 'BUSINESS' })).toBeVisible();
    expect(screen.getByText(/Drafts are never plan-gated/i)).toBeVisible();
    expect(screen.getAllByRole('button')).toHaveLength(4);
    screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
  });

  it('shows plan-specific publish reasons and reuses an eligible existing plan', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        website_id: 'website-id',
        page_count: 30,
        domain_type: 'ZYLORA_SUBDOMAIN',
        current_plan_code: 'BUSINESS',
        reuse_existing_subscription: true,
        can_request_publish: true,
        status: 'ELIGIBLE',
        recommended_plan_code: 'BUSINESS',
        plans: plans.map((plan) => ({
          plan,
          eligible: plan.code === 'BUSINESS',
          reasons:
            plan.code === 'BUSINESS'
              ? []
              : [{ code: 'PAGE_LIMIT', detail: `${plan.name} supports fewer pages.` }],
          is_current_plan: plan.code === 'BUSINESS',
        })),
      }),
    });
    vi.stubGlobal('fetch', fetcher);
    render(<PublishControls websiteId="website-id" status="DRAFT" />);
    fireEvent.click(screen.getByRole('button', { name: 'Check publishing' }));
    expect(await screen.findByText(/your existing plan will be reused/i)).toBeVisible();
    expect(screen.getByText('Basic supports fewer pages.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Request publish' })).toBeVisible();
    await waitFor(() =>
      expect(fetcher).toHaveBeenCalledWith(
        '/api/v1/websites/website-id/publish-evaluation?domain_type=ZYLORA_SUBDOMAIN',
        expect.objectContaining({ credentials: 'include' }),
      ),
    );
  });
});
