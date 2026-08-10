'use client';

import { useEffect, useState } from 'react';
import { Notice } from '@zylora/ui';

import { apiRequest } from '@/lib/api';
import { PublicFooter, PublicNavigation, PublicSite } from './public-site';
import { formatMoney, planFeatures, type PlanCatalog } from './commerce-types';
import styles from './commerce.module.css';

export function PricingCatalog() {
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    void apiRequest<PlanCatalog>('/api/v1/plans')
      .then(setCatalog)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Plans are unavailable.');
      });
  }, []);

  return (
    <PublicSite>
      <PublicNavigation />
      <main className={styles.main}>
        <section className={styles.hero}>
          <h1>Build freely. Choose a plan when you publish.</h1>
          <p>
            Every plan includes unlimited Lead capture and a monthly AI allowance. Draft and preview
            any-size websites before selecting the plan that fits publication.
          </p>
        </section>
        {error ? (
          <Notice tone="danger" title="Plans unavailable">
            {error}
          </Notice>
        ) : null}
        {!catalog && !error ? (
          <p className={styles.loading} role="status">
            Loading monthly plans…
          </p>
        ) : null}
        {catalog ? (
          <>
            <p className={styles.region}>
              Monthly pricing for {catalog.region === 'INDIA' ? 'India' : 'international customers'}{' '}
              · {catalog.currency}
            </p>
            <div className={styles.plans}>
              {catalog.items.map((plan) => (
                <article
                  className={`${styles.plan} ${plan.most_popular ? styles.planPopular : ''}`}
                  key={plan.id}
                >
                  {plan.most_popular ? <span className={styles.badge}>MOST POPULAR</span> : null}
                  <h2>{plan.name}</h2>
                  <p className={styles.description}>{plan.description}</p>
                  <p className={styles.price}>
                    {formatMoney(plan.price)} <small>/ month</small>
                  </p>
                  <ul className={styles.features}>
                    {planFeatures(plan).map((feature) => (
                      <li key={feature}>{feature}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </>
        ) : null}
      </main>
      <PublicFooter />
    </PublicSite>
  );
}
