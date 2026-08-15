import type { MetadataRoute } from 'next';

import { absoluteUrl } from '@/lib/seo';

type BlogItem = { slug: string; published_at: string };
type TemplateCatalog = { items: Array<{ slug: string }>; next_cursor: string | null };

export const dynamic = 'force-dynamic';

const staticPublicPaths = [
  '/',
  '/website-builder',
  '/ai-website-builder',
  '/features',
  '/solutions/small-business',
  '/solutions/freelancers',
  '/templates',
  '/pricing',
  '/blog',
  '/contact',
  '/privacy',
  '/terms',
  '/cookies',
  '/refunds',
] as const;

function fetchPublicApi(api: string, path: string) {
  return fetch(`${api}${path}`, { cache: 'no-store', signal: AbortSignal.timeout(2_500) });
}

function isSafeSlug(slug: string) {
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug);
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const api = process.env.API_INTERNAL_URL ?? 'http://127.0.0.1:8000';
  const entries = new Map<string, MetadataRoute.Sitemap[number]>();

  for (const path of staticPublicPaths) {
    const url = absoluteUrl(path);
    entries.set(url, { url });
  }

  try {
    const response = await fetchPublicApi(api, '/api/v1/blog/sitemap');
    if (response.ok) {
      const items = (await response.json()) as BlogItem[];
      for (const item of items) {
        if (!isSafeSlug(item.slug)) continue;
        const url = absoluteUrl(`/blog/${item.slug}`);
        entries.set(url, { url, lastModified: item.published_at });
      }
    }
  } catch {
    // The stable public sitemap remains available while optional API enrichment is unavailable.
  }

  try {
    let cursor: string | null = null;
    for (let page = 0; page < 1000; page += 1) {
      const query = new URLSearchParams({ limit: '48', sort: 'name' });
      if (cursor) query.set('cursor', cursor);
      const response = await fetchPublicApi(api, `/api/v1/templates?${query}`);
      if (!response.ok) break;
      const catalog = (await response.json()) as TemplateCatalog;
      for (const item of catalog.items) {
        if (!isSafeSlug(item.slug)) continue;
        const url = absoluteUrl(`/templates/${item.slug}`);
        entries.set(url, { url });
      }
      if (!catalog.next_cursor) break;
      cursor = catalog.next_cursor;
    }
  } catch {
    // Dynamic Template URLs are additive; keep the stable catalogue entry available.
  }

  return [...entries.values()];
}
