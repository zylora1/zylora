'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useEffect, useState } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';
import { TemplateCardPreview } from './template-card-preview';
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
type Category = { slug: string; name: string };

export function TemplateGallery({ createDraft = false }: { createDraft?: boolean }) {
  const router = useRouter();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [feature, setFeature] = useState('');
  const [sort, setSort] = useState('featured');
  const [creating, setCreating] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [activeParameters, setActiveParameters] = useState('');

  const load = async (parameters = '', append = false) => {
    setError('');
    try {
      const next = await apiRequest<Catalog>(`/api/v1/templates${parameters}`);
      setCatalog((current) =>
        append && current
          ? { items: [...current.items, ...next.items], next_cursor: next.next_cursor }
          : next,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The catalogue is unavailable.');
    }
  };

  useEffect(() => {
    void Promise.resolve().then(() => load());
    void apiRequest<Category[]>('/api/v1/templates/categories')
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const search = new URLSearchParams();
    if (query) search.set('query', query);
    if (category) search.set('category', category);
    if (feature) search.set('feature', feature);
    search.set('sort', sort);
    const parameters = `?${search}`;
    setActiveParameters(parameters);
    void load(parameters);
  };

  const loadMore = async () => {
    if (!catalog?.next_cursor) return;
    setLoadingMore(true);
    const search = new URLSearchParams(activeParameters.replace(/^\?/, ''));
    search.set('cursor', catalog.next_cursor);
    try {
      await load(`?${search}`, true);
    } finally {
      setLoadingMore(false);
    }
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
          {categories.map((item) => (
            <option key={item.slug} value={item.slug}>
              {item.name}
            </option>
          ))}
        </select>
        <select value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Sort">
          <option value="featured">Featured first</option>
          <option value="name">Name A-Z</option>
        </select>
        <select
          value={feature}
          onChange={(event) => setFeature(event.target.value)}
          aria-label="Feature"
        >
          <option value="">All capabilities</option>
          <option value="LEAD_CAPTURE">Lead capture</option>
          <option value="RESPONSIVE_PREVIEW">Responsive preview</option>
        </select>
        <button type="submit">Apply</button>
      </form>
      {error ? (
        <div className={styles.empty} role="alert">
          <h2>Catalogue unavailable</h2>
          <p>{error}</p>
          <button type="button" onClick={() => void load(activeParameters)}>
            Try again
          </button>
        </div>
      ) : null}
      {!catalog && !error ? (
        <div className={styles.empty} role="status">
          Loading approved Templates...
        </div>
      ) : null}
      {catalog && catalog.items.length === 0 ? (
        <div className={styles.empty}>
          <h2>No approved Templates match</h2>
          <p>Clear a filter or ask the Super Admin to publish a validated Template.</p>
        </div>
      ) : null}
      {catalog?.items.length ? (
        <>
          <div className={styles.grid} aria-live="polite">
            {catalog.items.map((item, index) => (
              <article className={styles.card} key={item.id}>
                <TemplateCardPreview item={item} index={index} />
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
                        {creating === item.slug ? 'Creating Draft...' : 'Use this Template'}
                      </button>
                    ) : null}
                  </div>
                </div>
              </article>
            ))}
          </div>
          {catalog.next_cursor ? (
            <div className={styles.loadMore}>
              <button type="button" disabled={loadingMore} onClick={() => void loadMore()}>
                {loadingMore ? 'Loading more Templates...' : 'Load more Templates'}
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  );
}
