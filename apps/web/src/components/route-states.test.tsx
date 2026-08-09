import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { WorkspaceRouteError, WorkspaceRouteLoading } from './route-states';

describe('workspace route states', () => {
  it('renders a geometry-matched loading state', () => {
    render(<WorkspaceRouteLoading />);
    expect(screen.getByRole('status', { name: 'Loading page' })).toBeVisible();
  });

  it('preserves a clear retry action for route failures', () => {
    const reset = vi.fn();
    render(<WorkspaceRouteError reset={reset} />);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
