'use client';

import { useEffect, useState } from 'react';
import { Notice } from '@zylora/ui';

import { apiRequest } from '@/lib/api';
import { formatMoney, planDisplayName, type PlanCatalog, type Subscription } from './commerce-types';
import styles from './commerce.module.css';

export function BillingPanel() {
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    void Promise.all([
      apiRequest<PlanCatalog>('/api/v1/plans'),
      apiRequest<Subscription>('/api/v1/billing/subscription'),
    ])
      .then(([nextCatalog, nextSubscription]) => {
        setCatalog(nextCatalog);
        setSubscription(nextSubscription);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Billing is unavailable.');
      });
  }, []);

  if (error)
    return (
      <Notice tone="danger" title="Billing unavailable">
        {error}
      </Notice>
    );
  if (!catalog || !subscription) return <p role="status">Loading billing details…</p>;
  return (
    <div className={styles.billing}>
      <section className={styles.subscription} aria-labelledby="current-plan-title">
        <div>
          <p className={styles.current}>CURRENT PLAN</p>
          <h2 id="current-plan-title">{subscription.plan_code}</h2>
          <p>
            {formatMoney(subscription.price)} per month · {subscription.state}
          </p>
          <p>
            Current period ends{' '}
            {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(
              new Date(subscription.current_period_end),
            )}
            .
          </p>
        </div>
        <div>
          <strong>{String(subscription.entitlements.ai_monthly_credits)}</strong>
          <p>AI credits / month</p>
        </div>
      </section>
      <Notice title="Drafts are never plan-gated">
        Build, edit, preview, transfer, and save any-size Draft. Page limits and custom-domain
        eligibility are evaluated only when you request publication.
      </Notice>
      <div className={styles.compactPlans}>
        {catalog.items.map((plan) => (
          <article className={styles.compactPlan} key={plan.id}>
            {plan.code === subscription.plan_code ? (
              <span className={styles.current}>CURRENT</span>
            ) : null}
            {plan.most_popular ? <span className={styles.badge}>MOST POPULAR</span> : null}
            <h3>{planDisplayName(plan)}</h3>
            <p>{formatMoney(plan.price)} / month</p>
            <p>
              {plan.entitlements.max_pages === 'UNLIMITED'
                ? 'Unlimited published pages'
                : `${String(plan.entitlements.max_pages)} published pages`}
            </p>
            <button className={styles.button} type="button" disabled>
              {plan.code === subscription.plan_code ? 'Current plan' : 'Checkout unavailable'}
            </button>
          </article>
        ))}
      </div>
      <Notice tone="warning" title="Paid checkout is not active yet">
        Zylora will not grant a paid capability until an approved payment provider verifies the
        exact server-side amount and currency. No placeholder checkout can activate a plan.
      </Notice>
    </div>
  );
}
