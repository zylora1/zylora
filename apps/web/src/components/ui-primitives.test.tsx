import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  ActionLink,
  Button,
  EmptyState,
  ErrorState,
  Notice,
  PageHeader,
  Skeleton,
  StatusBadge,
} from '@zylora/ui';

describe('Zylora UI primitives', () => {
  it('provides finite action variants and accessible states', () => {
    const click = vi.fn();
    render(
      <>
        <Button variant="danger" onClick={click}>
          Remove
        </Button>
        <ActionLink href="/next" variant="secondary">
          Continue
        </ActionLink>
        <StatusBadge tone="success">Ready</StatusBadge>
      </>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    expect(click).toHaveBeenCalledOnce();
    expect(screen.getByRole('button')).toHaveClass('z-button--danger');
    expect(screen.getByRole('link')).toHaveClass('z-button--secondary');
    expect(screen.getByText('Ready')).toHaveClass('z-status--success');
  });

  it('renders headers, notices, empty, error, and loading states semantically', () => {
    render(
      <>
        <PageHeader eyebrow="State" title="Websites" description="Your work" />
        <Notice title="Queued">This may take a moment.</Notice>
        <EmptyState title="Nothing here" description="Start when ready." />
        <ErrorState title="Could not load" description="Try again." />
        <Skeleton aria-label="Loading block" />
      </>,
    );
    expect(screen.getByRole('heading', { name: 'Websites' })).toBeVisible();
    expect(screen.getByRole('status')).toHaveTextContent('Queued');
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load');
    expect(screen.getByLabelText('Loading block')).toHaveAttribute('aria-hidden', 'true');
  });
});
