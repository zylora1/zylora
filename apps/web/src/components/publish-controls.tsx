'use client';

import { useState } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';
import type { PublishEvaluation } from './commerce-types';
import styles from './commerce.module.css';

type DomainType = 'ZYLORA_SUBDOMAIN' | 'CUSTOM';

export function PublishControls({ websiteId, status }: { websiteId: string; status: string }) {
  const [domainType, setDomainType] = useState<DomainType>('ZYLORA_SUBDOMAIN');
  const [evaluation, setEvaluation] = useState<PublishEvaluation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

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
          body: JSON.stringify({ domain_type: domainType }),
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
        <button
          className={styles.button}
          type="button"
          disabled={busy}
          onClick={() => void evaluate()}
        >
          {busy ? 'Checking…' : 'Check publishing'}
        </button>
        {evaluation?.can_request_publish &&
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
