'use client';

import { useState } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';
import type { PublishEvaluation } from './commerce-types';
import styles from './commerce.module.css';

type DomainType = 'ZYLORA_SUBDOMAIN' | 'CUSTOM';

type PublicationDomain = {
  id: string;
  hostname: string;
  state: string;
  tls_status: string;
  verification_record_name: string | null;
  verification_record_type: string | null;
  verification_record_value: string | null;
};
export function PublishControls({ websiteId, status }: { websiteId: string; status: string }) {
  const [domainType, setDomainType] = useState<DomainType>('ZYLORA_SUBDOMAIN');
  const [evaluation, setEvaluation] = useState<PublishEvaluation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [customHostname, setCustomHostname] = useState('');
  const [customDomain, setCustomDomain] = useState<PublicationDomain | null>(null);
  async function evaluate() {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      setEvaluation(
        await apiRequest<PublishEvaluation>(
          `/api/v1/websites/${websiteId}/publish-evaluation?domain_type=${domainType}`,
        ),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Publishing could not be evaluated.');
    } finally {
      setBusy(false);
    }
  }

  async function connectCustomDomain() {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const domain = await apiRequest<PublicationDomain>(
        `/api/v1/websites/${websiteId}/domains/custom`,
        {
          method: 'POST',
          headers: {
            'X-CSRF-Token': csrfToken('zylora_user_csrf') ?? '',
            'Idempotency-Key': crypto.randomUUID(),
          },
          body: JSON.stringify({ hostname: customHostname }),
        },
      );
      setCustomDomain(domain);
      setCustomHostname(domain.hostname);
      setMessage('Add the displayed DNS record, then check verification.');
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'The custom domain could not be requested.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function verifyCustomDomain() {
    if (!customDomain) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const domain = await apiRequest<PublicationDomain>(
        `/api/v1/websites/${websiteId}/domains/${customDomain.id}/verify`,
        {
          method: 'POST',
          headers: { 'X-CSRF-Token': csrfToken('zylora_user_csrf') ?? '' },
        },
      );
      setCustomDomain(domain);
      setMessage(
        domain.state === 'VERIFIED'
          ? 'Custom domain verified. It can now be selected for publishing.'
          : 'Verification is still pending. Confirm the DNS record and try again.',
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'The custom domain could not be verified.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    setBusy(true);
    setError('');
    try {
      const result = await apiRequest<{ message: string }>(
        `/api/v1/websites/${websiteId}/publish`,
        {
          method: 'POST',
          headers: {
            'X-CSRF-Token': csrfToken('zylora_user_csrf') ?? '',
            'Idempotency-Key': crypto.randomUUID(),
          },
          body: JSON.stringify({
            domain_type: domainType,
            ...(domainType === 'CUSTOM' ? { hostname: customDomain?.hostname } : {}),
          }),
        },
      );
      setMessage(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Publishing could not be requested.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.publish} aria-label="Publishing eligibility">
      <div className={styles.publishRow}>
        <label htmlFor={`domain-${websiteId}`}>Publication address</label>
        <select
          id={`domain-${websiteId}`}
          value={domainType}
          onChange={(event) => {
            setDomainType(event.target.value as DomainType);
            setEvaluation(null);
          }}
        >
          <option value="ZYLORA_SUBDOMAIN">Zylora subdomain</option>
          <option value="CUSTOM">Custom domain</option>
        </select>
        {domainType === 'CUSTOM' ? (
          <div className={styles.customDomain}>
            <label htmlFor={`custom-domain-${websiteId}`}>Custom domain</label>
            <input
              id={`custom-domain-${websiteId}`}
              value={customHostname}
              onChange={(event) => {
                setCustomHostname(event.target.value);
                setCustomDomain(null);
              }}
              placeholder="www.example.com"
              inputMode="url"
            />
            <button
              className={styles.button}
              type="button"
              disabled={busy || !customHostname.trim()}
              onClick={() => void connectCustomDomain()}
            >
              Connect domain
            </button>
            {customDomain ? (
              <div className={styles.domainStatus}>
                <strong>{customDomain.state.replaceAll('_', ' ')}</strong>
                {customDomain.verification_record_name && customDomain.verification_record_value ? (
                  <p>
                    Add {customDomain.verification_record_type ?? 'TXT'} record{' '}
                    <code>{customDomain.verification_record_name}</code> ={' '}
                    <code>{customDomain.verification_record_value}</code>
                  </p>
                ) : null}
                {customDomain.state !== 'VERIFIED' ? (
                  <button
                    className={styles.button}
                    type="button"
                    disabled={busy}
                    onClick={() => void verifyCustomDomain()}
                  >
                    Check verification
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
        <button
          className={styles.button}
          type="button"
          disabled={busy}
          onClick={() => void evaluate()}
        >
          {busy ? 'Checking…' : 'Check publishing'}
        </button>
        {evaluation?.can_request_publish &&
        (domainType === 'ZYLORA_SUBDOMAIN' || customDomain?.state === 'VERIFIED') &&
        !['PUBLISHING', 'PUBLISHED', 'UNPUBLISHING'].includes(status) ? (
          <button
            className={styles.button}
            type="button"
            disabled={busy}
            onClick={() => void publish()}
          >
            Request publish
          </button>
        ) : null}
      </div>
      {evaluation ? (
        <>
          <p>
            {evaluation.page_count} pages · Current plan {evaluation.current_plan_code} ·{' '}
            {evaluation.reuse_existing_subscription
              ? 'your existing plan will be reused'
              : evaluation.can_request_publish
                ? 'eligible to publish'
                : `recommended: ${evaluation.recommended_plan_code ?? 'no eligible plan'}`}
          </p>
          <ul className={styles.evaluation}>
            {evaluation.plans.map((item) => (
              <li data-eligible={item.eligible} key={item.plan.id}>
                <strong>{item.plan.name}</strong>
                {item.eligible ? 'Eligible' : item.reasons.map((reason) => reason.detail).join(' ')}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className={styles.success} role="status">
          {message}
        </p>
      ) : null}
    </section>
  );
}
