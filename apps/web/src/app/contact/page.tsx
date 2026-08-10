'use client';

import { FormEvent, useCallback, useState } from 'react';

import { PublicFooter, PublicNavigation, PublicSite } from '@/components/public-site';
import { TurnstileWidget } from '@/components/turnstile-widget';
import { apiRequest } from '@/lib/api';

export default function ContactPage() {
  const [token, setToken] = useState<string | null>(null);
  const [required, setRequired] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [sending, setSending] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const onRequirement = useCallback((next: boolean) => setRequired(next), []);
  const onError = useCallback((message: string) => setError(message), []);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    if (required && !token) {
      setError('Complete the security verification before sending.');
      return;
    }
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setSending(true);
    try {
      await apiRequest('/api/v1/public/contact', {
        method: 'POST',
        body: JSON.stringify({
          name: form.get('name'),
          email: form.get('email'),
          message: form.get('message'),
          turnstile_token: token,
        }),
      });
      formElement.reset();
      setToken(null);
      setResetKey((value) => value + 1);
      setSuccess('Thanks — your message is safely queued for the Zylora team.');
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'We could not send your message. Please try again.',
      );
    } finally {
      setSending(false);
    }
  };
  return (
    <PublicSite>
      <PublicNavigation />
      <main className="contact-page">
        <section>
          <p className="eyebrow">Talk to Zylora</p>
          <h1>Tell us what you’re building.</h1>
          <p>
            Questions about the product, a purchase, or a Website workflow? Send a short note and
            the team will review it.
          </p>
        </section>
        <form onSubmit={submit} noValidate>
          <label>
            Name
            <input name="name" required maxLength={160} />
          </label>
          <label>
            Email
            <input name="email" type="email" required maxLength={320} />
          </label>
          <label>
            Message
            <textarea name="message" required minLength={20} maxLength={5000} />
          </label>
          <TurnstileWidget
            action="contact"
            resetKey={resetKey}
            onToken={setToken}
            onRequirementChange={onRequirement}
            onError={onError}
          />
          {error ? <p role="alert">{error}</p> : null}
          {success ? <p role="status">{success}</p> : null}
          <button disabled={sending}>{sending ? 'Sending…' : 'Send message'}</button>
        </form>
      </main>
      <PublicFooter />
    </PublicSite>
  );
}
