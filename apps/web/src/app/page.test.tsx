import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import HomePage from './page';

describe('HomePage', () => {
  it('presents the Phase 2 identity entry points', () => {
    render(<HomePage />);

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: 'Choose the shape. Make it unmistakably yours.',
      }),
    ).toBeVisible();
    expect(screen.getByRole('link', { name: 'Explore Templates' })).toHaveAttribute(
      'href',
      '/templates',
    );
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
    expect(screen.queryByText(/trusted by/i)).not.toBeInTheDocument();
  });
});
