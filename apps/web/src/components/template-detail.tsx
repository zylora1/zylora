'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { apiRequest } from '@/lib/api';
import type { TemplateSummary } from './template-gallery';
import styles from './template-platform.module.css';

export function TemplateDetail({ slug }: { slug: string }) {
  const [item, setItem] = useState<TemplateSummary | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    apiRequest<TemplateSummary>(`/api/v1/templates/${slug}`)
      .then(setItem)
      .catch((reason) =>
        setError(reason instanceof Error ? reason.message : 'Template unavailable.'),
      );
  }, [slug]);
  if (error)
    return (
      <div className={styles.empty} role="alert">
        <h1>Template unavailable</h1>
        <p>{error}</p>
        <Link href="/templates">Back to catalogue</Link>
      </div>
    );
  if (!item) return <div className={styles.empty}>Loading Template details…</div>;
  return (
    <section className={styles.catalogHero}>
      <div>
        <p>{item.category}</p>
        <h1>{item.name}</h1>
      </div>
      <div>
        <p>{item.summary}</p>
        <div className={styles.tags}>
          {item.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
        <div className={styles.cardLinks}>
          <Link href={`/templates/${item.slug}/preview?version=${item.version}`}>
            Open responsive preview
          </Link>
          <Link href="/app/templates">Choose from User portal</Link>
        </div>
      </div>
    </section>
  );
}
