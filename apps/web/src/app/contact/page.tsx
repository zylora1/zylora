'use client';

import { FormEvent, useCallback, useState } from 'react';

import { PublicFooter, PublicNavigation, PublicSite } from '@/components/public-site';
import { TurnstileWidget } from '@/components/turnstile-widget';
import { apiRequest } from '@/lib/api';

interface ProEnquiryResponse {
  id: string;
  reference_id: string;
  name: string;
  email: string;
  website_type: string;
  preferred_contact_time: string;
  status: string;
}

export default function ContactPage() {
  const [token, setToken] = useState<string | null>(null);
  const [required, setRequired] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [referenceId, setReferenceId] = useState('');
  const [sending, setSending] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const onRequirement = useCallback((next: boolean) => setRequired(next), []);
  const onError = useCallback((message: string) => setError(message), []);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    setReferenceId('');
    if (required && !token) {
      setError('Complete the security verification before sending.');
      return;
    }
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setSending(true);
    try {
      const result = await apiRequest<ProEnquiryResponse>('/api/v1/public/pro-enquiry', {
        method: 'POST',
        body: JSON.stringify({
          name: form.get('name'),
          email: form.get('email'),
          website_type: form.get('website_type'),
          preferred_contact_time: form.get('preferred_contact_time'),
          company_website_url: (form.get('company_website_url') as string) || null,
          turnstile_token: token,
        }),
      });
      formElement.reset();
      setToken(null);
      setResetKey((value) => value + 1);
      setReferenceId(result.reference_id);
      setSuccess(
        "Your Pro request has been received ✓ We've sent a confirmation to your email. Our team will contact you around your preferred time.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'We could not send your request. Please try again.',
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
          <p className="eyebrow">Zylora Pro Managed Service</p>
          <h1>Get in Touch for Pro Sales</h1>
          <p>
            Tell us what kind of website you need. Our team will build and manage your custom web
            experience.
          </p>
        </section>
        <form onSubmit={submit} noValidate>
          <div style={{ display: 'none' }} aria-hidden="true">
            <input name="company_website_url" type="text" tabIndex={-1} autoComplete="off" />
          </div>
          <label>
            Name
            <input
              name="name"
              required
              minLength={2}
              maxLength={100}
              placeholder="Your full name"
            />
          </label>
          <label>
            Email
            <input
              name="email"
              type="email"
              required
              maxLength={320}
              placeholder="your.email@example.com"
            />
          </label>
          <label>
            Type of website you want
            <input
              name="website_type"
              required
              minLength={2}
              maxLength={150}
              placeholder="e.g. Dental clinic website, restaurant website, portfolio, school website"
            />
          </label>
          <label>
            Preferred contact time
            <input
              name="preferred_contact_time"
              required
              maxLength={160}
              placeholder="e.g. Weekdays 2–5 PM IST"
            />
          </label>
          <TurnstileWidget
            action="pro_enquiry"
            resetKey={resetKey}
            onToken={setToken}
            onRequirementChange={onRequirement}
            onError={onError}
          />
          {error ? <p role="alert">{error}</p> : null}
          {success ? (
            <div role="status" className="pro-success-notice">
              <p>{success}</p>
              {referenceId ? (
                <p>
                  <strong>Reference ID:</strong> {referenceId}
                </p>
              ) : null}
            </div>
          ) : null}
          <button disabled={sending}>{sending ? 'Submitting…' : 'Submit Pro Request'}</button>
        </form>
      </main>
      <PublicFooter />
    </PublicSite>
  );
}
