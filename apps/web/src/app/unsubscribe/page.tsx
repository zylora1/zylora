'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import { apiRequest } from '@/lib/api';

function UnsubscribeForm() {
  const search = useSearchParams();
  const token = search.get('token') ?? '';
  const [message, setMessage] = useState(
    token ? '' : 'This unsubscribe link is missing or invalid.',
  );
  const [complete, setComplete] = useState(false);

  const unsubscribe = async () => {
    try {
      await apiRequest<void>('/api/v1/public/marketing/unsubscribe', {
        method: 'POST',
        body: JSON.stringify({ token }),
      });
      setComplete(true);
      setMessage('You have been unsubscribed from Zylora marketing email.');
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'We could not update your preference.');
    }
  };

  return (
    <main className="blog-shell unsubscribe-page">
      <section className="unsubscribe-card" aria-live="polite">
        <p className="eyebrow">Email preferences</p>
        <h1>Marketing email</h1>
        <p>
          This preference affects Zylora marketing campaigns only. Account, security, and other
          required transactional email remains separate.
        </p>
        {message ? (
          <p className={complete ? 'unsubscribe-success' : 'blog-message'}>{message}</p>
        ) : null}
        {!complete && token ? (
          <button type="button" onClick={() => void unsubscribe()}>
            Unsubscribe from marketing
          </button>
        ) : null}
      </section>
    </main>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={<main className="blog-shell blog-message">Loading preferences...</main>}>
      <UnsubscribeForm />
    </Suspense>
  );
}
