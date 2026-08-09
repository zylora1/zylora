'use client';

import { Button, ErrorState, Skeleton } from '@zylora/ui';

export function WorkspaceRouteLoading() {
  return (
    <div className="route-loading" role="status" aria-label="Loading page">
      <Skeleton className="route-loading__eyebrow" />
      <Skeleton className="route-loading__title" />
      <Skeleton className="route-loading__description" />
      <Skeleton className="route-loading__panel" />
    </div>
  );
}

export function WorkspaceRouteError({ reset }: { reset: () => void }) {
  return (
    <ErrorState
      title="This page could not be loaded"
      description="Your session and other workspace pages are unchanged. Try this page again."
      action={
        <Button variant="secondary" onClick={reset}>
          Try again
        </Button>
      }
    />
  );
}
