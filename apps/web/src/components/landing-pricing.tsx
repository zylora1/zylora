'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import { apiRequest } from '@/lib/api';
import { formatMoney, type PlanCatalog } from './commerce-types';
import styles from './landing-page.module.css';

export function LandingPricing() {
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);

  useEffect(() => {
    void apiRequest<PlanCatalog>('/api/v1/plans')
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);

  return (
    <div className={styles.pricingFrame}>
      <div className={styles.pricingIntro}>
        <p className={styles.eyebrow}>Monthly plans</p>
        <h2>Build first. Choose when you publish.</h2>
        <p>
          Draft and preview before committing to a publishing plan. The server evaluates the plan
          your live website actually needs.
        </p>
        <Link className={styles.textLink} href="/pricing">
          Compare plans <span aria-hidden="true">↗</span>
        </Link>
      </div>
      <div className={styles.planList} aria-live="polite">
        {catalog ? (
          catalog.items.map((plan) => (
            <article key={plan.id} data-popular={plan.most_popular}>
              <div>
                <span>{plan.name}</span>
                {plan.most_popular ? <small>MOST POPULAR</small> : null}
              </div>
              <strong>
                {formatMoney(plan.price)} <small>/ month</small>
              </strong>
            </article>
          ))
        ) : (
          <>
            <article className={styles.planSkeleton} aria-label="Loading plan pricing" />
            <article className={styles.planSkeleton} aria-hidden="true" />
            <article className={styles.planSkeleton} aria-hidden="true" />
            <article className={styles.planSkeleton} aria-hidden="true" />
          </>
        )}
      </div>
    </div>
  );
}
