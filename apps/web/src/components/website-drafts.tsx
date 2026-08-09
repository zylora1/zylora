'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Notice, StatusBadge } from '@zylora/ui';

import { apiRequest } from '@/lib/api';
import { PublishControls } from './publish-controls';
import styles from './template-platform.module.css';

type Website = {
  id: string;
  display_name: string;
  status: string;
  pages: Array<{
    id: string;
    name: string;
    path: string;
    is_home: boolean;
    show_in_navigation: boolean;
  }>;
  created_at: string;
};

export function WebsiteDrafts() {
  const [items, setItems] = useState<Website[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    void Promise.resolve().then(async () => {
      try {
        setItems((await apiRequest<{ items: Website[] }>('/api/v1/websites')).items);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : 'Drafts are unavailable.');
      }
    });
  }, []);
  if (error)
    return (
      <Notice tone="danger" title="Drafts unavailable">
        {error}
      </Notice>
    );
  if (!items) return <p role="status">Loading your Drafts…</p>;
  if (items.length === 0)
    return (
      <div className={styles.empty}>
        <h2>No Draft Websites yet</h2>
        <p>
          Select an approved Template to create a complete private Draft. No plan or payment is
          required.
        </p>
        <Link href="/app/templates">Choose a Template</Link>
      </div>
    );
  return (
    <div className={styles.adminStack}>
      {items.map((item) => (
        <article className={styles.adminTemplate} key={item.id}>
          <header>
            <div>
              <h2>{item.display_name}</h2>
              <p>{item.pages.length} pages · Created from an approved Template</p>
            </div>
            <StatusBadge tone="info">{item.status}</StatusBadge>
          </header>
          <div className={styles.tags}>
            {item.pages
              .filter((page) => page.show_in_navigation)
              .slice(0, 8)
              .map((page) => (
                <span key={page.id}>{page.path}</span>
              ))}
          </div>
          <p>Organize every page in the compact Website map. Plans apply only when publishing.</p>
          <Link href={'/app/websites/' + item.id + '/edit'}>Manage pages</Link>
          <PublishControls websiteId={item.id} status={item.status} />
        </article>
      ))}
    </div>
  );
}
