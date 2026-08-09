'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useEffect, useState } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';
import styles from './template-platform.module.css';

export type TemplateSummary = {
  id: string;
  slug: string;
  name: string;
  summary: string;
  category: string;
  category_slug: string;
  tags: string[];
  features: string[];
  version: number;
  status: string;
  featured_order: number;
};
type Catalog = { items: TemplateSummary[]; next_cursor: string | null };

const swatches = ['#164E46', '#2C342F', '#6B2E24', '#203D63', '#67412C'];

export function TemplateGallery({ createDraft = false }: { createDraft?: boolean }) {
  const router = useRouter();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [sort, setSort] = useState('featured');
  const [creating, setCreating] = useState<string | null>(null);
  const load = async (parameters = '') => {
    setError('');
    try {
      setCatalog(await apiRequest<Catalog>(`/api/v1/templates${parameters}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The catalogue is unavailable.');
    }
  };
  useEffect(() => {
    void Promise.resolve().then(() => load());
  }, []);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const search = new URLSearchParams();
    if (query) search.set('query', query);
    if (category) search.set('category', category);
    search.set('sort', sort);
    void load(`?${search}`);
  };
  const createWebsite = async (slug: string) => {
    setCreating(slug);
    setError('');
    try {
      await apiRequest(`/api/v1/templates/${slug}/instantiate`, {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken('zylora_user_csrf') ?? '' },
        body: JSON.stringify({}),
      });
      router.push('/app/websites');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The Draft could not be created.');
      setCreating(null);
    }
  };
  const categories = Array.from(
    new Map((catalog?.items ?? []).map((item) => [item.category_slug, item.category])).entries(),
  );
  return (
    <>
      <form className={styles.filters} onSubmit={submit} aria-label="Filter Templates">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by name or purpose"
          aria-label="Search Templates"
        />
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          aria-label="Category"
        >
          <option value="">All categories</option>
          {categories.map(([slug, name]) => (
            <option key={slug} value={slug}>
              {name}
            </option>
          ))}
        </select>
        <select value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Sort">
          <option value="featured">Featured first</option>
          <option value="name">Name A–Z</option>
        </select>
        <select aria-label="Feature" disabled>
          <option>All capabilities</option>
        </select>
        <button type="submit">Apply</button>
      </form>
      {error ? (
        <div className={styles.empty} role="alert">
          <h2>Catalogue unavailable</h2>
          <p>{error}</p>
          <button type="button" onClick={() => void load()}>
            Try again
          </button>
        </div>
      ) : null}
      {!catalog && !error ? (
        <div className={styles.empty} role="status">
          Loading approved Templates…
        </div>
      ) : null}
      {catalog && catalog.items.length === 0 ? (
        <div className={styles.empty}>
          <h2>No approved Templates match</h2>
          <p>Clear a filter or ask the Super Admin to publish a validated Template.</p>
        </div>
      ) : null}
      {catalog?.items.length ? (
        <div className={styles.grid}>
          {catalog.items.map((item, index) => (
            <article className={styles.card} key={item.id}>
              <div
                className={styles.cardPreview}
                style={
                  { '--card-primary': swatches[index % swatches.length] } as React.CSSProperties
                }
              >
                <span>{item.category}</span>
                <strong>{item.name}</strong>
              </div>
              <div className={styles.cardBody}>
                <h2>{item.name}</h2>
                <p>{item.summary}</p>
                <div className={styles.tags}>
                  {item.tags.map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>
                <div className={styles.cardLinks}>
                  <Link href={`/templates/${item.slug}`}>View details</Link>
                  <Link href={`/templates/${item.slug}/preview?version=${item.version}`}>
                    Preview
                  </Link>{' '}
                  {createDraft ? (
                    <button
                      type="button"
                      disabled={creating === item.slug}
                      onClick={() => void createWebsite(item.slug)}
                    >
                      {creating === item.slug ? 'Creating Draft…' : 'Use this Template'}
                    </button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </>
  );
}
