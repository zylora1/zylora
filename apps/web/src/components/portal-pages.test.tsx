import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { adminSections, userSections } from './portal-navigation';
import { AdminHomePage, AdminSectionPage, UserHomePage, UserSectionPage } from './portal-pages';

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

  it('renders honest User and Admin empty states from finite route definitions', () => {
    render(<UserSectionPage section={userSections.find(({ slug }) => slug === 'analytics')!} />);
    expect(
      screen.getByRole('heading', { name: 'Analytics begins with real traffic' }),
    ).toBeVisible();

    render(<AdminSectionPage section={adminSections.find(({ slug }) => slug === 'health')!} />);
    expect(
      screen.getByRole('heading', { name: 'Detailed health data is not connected' }),
    ).toBeVisible();
  });

  it('keeps the Admin overview evidence-led and free of synthetic status', () => {
    render(<AdminHomePage />);
    expect(screen.getByRole('heading', { level: 1, name: 'Platform overview' })).toBeVisible();
    expect(screen.getByText(/No synthetic operational summary/i)).toBeVisible();
  });
});
