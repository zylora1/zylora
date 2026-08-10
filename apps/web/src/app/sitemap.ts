import type { MetadataRoute } from 'next';

type BlogItem = { slug: string; published_at: string };
type TemplateCatalog = { items: Array<{ slug: string }>; next_cursor: string | null };

export const dynamic = 'force-dynamic';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = process.env.NEXT_PUBLIC_WEB_ORIGIN ?? 'http://localhost:3000';
  const api = process.env.API_INTERNAL_URL ?? 'http://127.0.0.1:8000';
  const publicPages = [
    '',
    '/templates',
    '/pricing',
    '/blog',
    '/contact',
    '/privacy',
    '/terms',
    '/cookies',
    '/refunds',
  ].map((path) => ({ url: `${origin}${path}`, lastModified: new Date() }));
  const entries: MetadataRoute.Sitemap = [...publicPages];

  try {
    const response = await fetch(`${api}/api/v1/blog/sitemap`, { cache: 'no-store' });
    if (response.ok) {
      const items = (await response.json()) as BlogItem[];
      entries.push(
        ...items.map((item) => ({
          url: `${origin}/blog/${item.slug}`,
          lastModified: item.published_at,
        })),
      );
    }
  } catch {
    // An unavailable API must not make the base public sitemap unavailable.
  }

  try {
    let cursor: string | null = null;
    for (let page = 0; page < 1000; page += 1) {
      const query = new URLSearchParams({ limit: '48', sort: 'name' });
      if (cursor) query.set('cursor', cursor);
      const response = await fetch(`${api}/api/v1/templates?${query}`, { cache: 'no-store' });
      if (!response.ok) break;
      const catalog = (await response.json()) as TemplateCatalog;
      entries.push(...catalog.items.map((item) => ({ url: `${origin}/templates/${item.slug}` })));
      if (!catalog.next_cursor) break;
      cursor = catalog.next_cursor;
    }
  } catch {
    // Dynamic Template URLs are additive; keep the stable catalogue entry available.
  }

  return entries;
}
