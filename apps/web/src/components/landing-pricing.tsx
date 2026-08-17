'use client';

import { Check } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { apiRequest } from '@/lib/api';
import { formatMoney, planDisplayName, planFeatures, type PlanCatalog } from './commerce-types';
import styles from './landing-page.module.css';

export function LandingPricing() {
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);

  useEffect(() => {
    void apiRequest<PlanCatalog>('/api/v1/plans')
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);

  return (
    <section className={styles.pricingSection} id="pricing">
      <div className={styles.pricingHeader}>
        <span className="eyebrow" style={{ color: 'var(--z-color-brand)' }}>
          Transparent Commercial Model
        </span>
        <h2>Build for free. Choose your plan when publishing.</h2>
        <p>
          Every account includes unlimited private drafts. Upgrade only when you publish your live
          website to custom domains or unlock higher quotas.
        </p>
      </div>

      <div className={styles.pricingGrid}>
        {catalog ? (
          catalog.items.map((plan) => {
            const features = planFeatures(plan);
            const isPro = plan.code === 'BUSINESS' || plan.code === 'PRO';
            const name = planDisplayName(plan);
            return (
              <article
                key={plan.id}
                className={styles.planCard}
                data-popular={plan.most_popular}
                style={{
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                  padding: '2rem 1.5rem',
                  borderRadius: 'var(--z-radius-lg)',
                  background: plan.most_popular
                    ? 'var(--z-color-surface-raised)'
                    : 'var(--z-color-surface)',
                  border: plan.most_popular
                    ? '2px solid var(--z-color-brand)'
                    : '1px solid var(--z-color-border)',
                  boxShadow: plan.most_popular
                    ? '0 10px 30px rgba(16, 185, 129, 0.12)'
                    : 'var(--z-shadow-card)',
                }}
              >
                {plan.most_popular ? (
                  <span
                    style={{
                      position: 'absolute',
                      top: '-0.75rem',
                      right: '1.25rem',
                      padding: '0.25rem 0.6rem',
                      borderRadius: 'var(--z-radius-round)',
                      background: 'var(--z-color-brand)',
                      color: '#06110d',
                      fontSize: '0.65rem',
                      fontWeight: 900,
                      letterSpacing: '0.08em',
                    }}
                  >
                    MOST POPULAR
                  </span>
                ) : null}

                <header style={{ marginBottom: '1.5rem' }}>
                  <h3
                    style={{
                      margin: '0 0 0.4rem',
                      fontSize: '1.3rem',
                      fontWeight: 600,
                      color: '#fff',
                    }}
                  >
                    {name}
                  </h3>
                  <p
                    style={{
                      margin: 0,
                      fontSize: '0.825rem',
                      color: 'var(--z-color-ink-muted)',
                      minHeight: '2.4rem',
                    }}
                  >
                    {plan.description}
                  </p>
                </header>

                <div style={{ marginBottom: '1.5rem' }}>
                  <strong
                    style={{
                      fontSize: isPro ? '2rem' : '2.5rem',
                      fontWeight: 700,
                      color: '#fff',
                      letterSpacing: '-0.04em',
                    }}
                  >
                    {isPro ? 'Custom' : formatMoney(plan.price)}
                  </strong>
                  {!isPro ? (
                    <span
                      style={{
                        fontSize: '0.85rem',
                        color: 'var(--z-color-ink-muted)',
                        marginLeft: '0.4rem',
                      }}
                    >
                      / month
                    </span>
                  ) : (
                    <span
                      style={{
                        fontSize: '0.85rem',
                        color: 'var(--z-color-brand)',
                        marginLeft: '0.4rem',
                        fontWeight: 700,
                      }}
                    >
                      Managed by experts
                    </span>
                  )}
                </div>

                <ul
                  style={{
                    listStyle: 'none',
                    padding: 0,
                    margin: '0 0 2rem',
                    display: 'grid',
                    gap: '0.7rem',
                    flex: 1,
                  }}
                >
                  {features.map((feature, idx) => (
                    <li
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.6rem',
                        fontSize: '0.825rem',
                        color: 'var(--z-color-ink-soft)',
                      }}
                    >
                      <Check size={16} style={{ color: 'var(--z-color-brand)', flexShrink: 0 }} />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  className={
                    plan.most_popular
                      ? 'z-button z-button--primary'
                      : 'z-button z-button--secondary'
                  }
                  href={isPro ? '/contact' : '/signup'}
                  style={{ width: '100%', minHeight: '2.75rem', textDecoration: 'none' }}
                >
                  {isPro ? 'Get in Touch' : plan.code === 'FREE' ? 'Start Free' : 'Get Started'}
                </Link>
              </article>
            );
          })
        ) : (
          <div
            style={{
              gridColumn: '1 / -1',
              padding: '3rem',
              textAlign: 'center',
              color: 'var(--z-color-ink-muted)',
            }}
          >
            Loading plans and pricing configuration...
          </div>
        )}
      </div>
    </section>
  );
}
