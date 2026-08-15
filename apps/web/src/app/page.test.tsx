import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import HomePage from './page';
const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));

describe('HomePage', () => {
  it('presents both production website creation paths', () => {
    render(<HomePage />);

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: 'Build a professional website your way.',
      }),
    ).toBeVisible();
    expect(screen.getAllByRole('link', { name: 'Explore Templates' })[0]).toHaveAttribute(
      'href',
      '/templates',
    );
    expect(screen.getByRole('button', { name: 'Build this website with AI' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
    expect(screen.queryByText(/trusted by/i)).not.toBeInTheDocument();
  });
});
