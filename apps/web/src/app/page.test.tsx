import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import HomePage from './page';

describe('HomePage', () => {
  it('presents the Phase 2 identity entry points', () => {
    render(<HomePage />);

    expect(
      screen.getByRole('heading', { level: 1, name: 'A considered home for what you do.' }),
    ).toBeVisible();
    expect(screen.getByRole('link', { name: 'Create account' })).toHaveAttribute('href', '/signup');
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
    expect(screen.queryByText(/trusted by/i)).not.toBeInTheDocument();
  });
});
