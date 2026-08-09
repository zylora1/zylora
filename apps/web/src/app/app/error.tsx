'use client';

import { WorkspaceRouteError } from '@/components/route-states';

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <WorkspaceRouteError reset={reset} />;
}
