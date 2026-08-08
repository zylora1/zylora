import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import FoundationPage from './page';

describe('FoundationPage', () => {
  it('presents the honest Phase 1 platform boundary', () => {
    render(<FoundationPage />);

    expect(screen.getByRole('heading', { level: 1, name: 'Platform foundation' })).toBeVisible();
    expect(screen.getByRole('list', { name: 'Foundation components' })).toBeVisible();
    expect(screen.queryByText(/trusted by/i)).not.toBeInTheDocument();
  });
});
