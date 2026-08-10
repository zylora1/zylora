import type { MetadataRoute } from 'next';

export const dynamic = 'force-dynamic';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = process.env.NEXT_PUBLIC_WEB_ORIGIN ?? 'http://localhost:3000';
  const api = process.env.API_INTERNAL_URL ?? 'http://127.0.0.1:8000';
  try {
    const response = await fetch(`${api}/api/v1/blog/sitemap`, { cache: 'no-store' });
    if (!response.ok) return [];
    const items = (await response.json()) as Array<{ slug: string; published_at: string }>;
    return items.map((item) => ({
      url: `${origin}/blog/${item.slug}`,
      lastModified: item.published_at,
    }));
  } catch {
    return [];
  }
}
