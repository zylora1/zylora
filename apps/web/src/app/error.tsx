'use client';

import { Button, ErrorState } from '@zylora/ui';
import Link from 'next/link';

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="root-error-page">
      <ErrorState
        title="We could not load this page"
        description="Nothing has been changed. You can retry the request or return to the Zylora home page."
        action={
          <span className="root-error-page__actions">
            <Button variant="secondary" onClick={reset}>
              Try again
            </Button>
            <Link href="/">Back home</Link>
          </span>
        }
      />
    </main>
  );
}
