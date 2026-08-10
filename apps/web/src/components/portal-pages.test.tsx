import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { adminSections, userSections } from './portal-navigation';
import { AdminHomePage, AdminSectionPage, UserHomePage, UserSectionPage } from './portal-pages';

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'zylora_user_csrf=; Max-Age=0';
  document.cookie = 'zylora_admin_csrf=; Max-Age=0';
});

describe('portal pages', () => {
  it('uses the required first-time CTA without fake analytics', () => {
    render(<UserHomePage />);
    expect(
      screen.getByRole('heading', { level: 1, name: 'Publish your first website' }),
    ).toBeVisible();
    expect(screen.getByRole('link', { name: /Choose a Template/i })).toHaveAttribute(
      'href',
      '/app/templates',
    );
    expect(screen.getByText('Choose → Customize → Publish')).toBeVisible();
    expect(screen.getByText(/does not fill a new account with invented charts/i)).toBeVisible();
    expect(screen.queryByText(/0%|0 leads|revenue/i)).not.toBeInTheDocument();
  });

  it('renders honest User and Admin empty states from finite route definitions', async () => {
    document.cookie = 'zylora_user_csrf=portal-test';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ has_published_website: true, has_meaningful_data: false, points: [] }),
      }),
    );
    render(<UserSectionPage section={userSections.find(({ slug }) => slug === 'analytics')!} />);
    expect(await screen.findByText('No analytics yet')).toBeVisible();

    render(<AdminSectionPage section={adminSections.find(({ slug }) => slug === 'health')!} />);
    expect(screen.getByText('Checking live operational dependencies…')).toBeVisible();
  });

  it('keeps the Admin overview evidence-led while real data is loading', () => {
    render(<AdminHomePage />);
    expect(screen.getByRole('heading', { level: 1, name: 'Platform overview' })).toBeVisible();
    expect(screen.getByText('Loading measured operational state…')).toBeVisible();
  });
});
