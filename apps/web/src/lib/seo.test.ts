import { afterEach, describe, expect, it, vi } from 'vitest';

import robots, { privateRobotPaths } from '@/app/robots';
import sitemap from '@/app/sitemap';
import { absoluteUrl, createPageMetadata, createPrivateMetadata, serializeJsonLd } from './seo';

describe('public SEO architecture', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('creates deliberate canonical and social metadata from one page definition', () => {
    vi.stubEnv('NEXT_PUBLIC_WEB_ORIGIN', 'https://www.zylora.example');
    const metadata = createPageMetadata({
      title: 'Website Builder',
      description: 'A precise page description.',
      path: '/website-builder',
    });

    expect(metadata.alternates).toEqual({ canonical: '/website-builder' });
    expect(metadata.openGraph).toMatchObject({
      title: 'Website Builder',
      description: 'A precise page description.',
      url: '/website-builder',
    });
    expect(metadata.twitter).toMatchObject({
      card: 'summary_large_image',
      title: 'Website Builder',
    });
    expect(absoluteUrl('/features')).toBe('https://www.zylora.example/features');
  });

  it('marks identity and application surfaces as private', () => {
    expect(createPrivateMetadata('Sign in', 'Private route').robots).toMatchObject({
      index: false,
      follow: false,
      nocache: true,
    });
  });

  it('fails closed for crawling unless production indexing is explicitly enabled', () => {
    vi.stubEnv('NEXT_PUBLIC_WEB_ORIGIN', 'https://www.zylora.example');
    vi.stubEnv('NEXT_PUBLIC_SEARCH_INDEXING_ENABLED', 'false');
    const safePolicy = robots();
    expect(safePolicy.rules).toEqual([{ userAgent: '*', disallow: ['/', ...privateRobotPaths] }]);

    vi.stubEnv('NEXT_PUBLIC_SEARCH_INDEXING_ENABLED', 'true');
    const productionPolicy = robots();
    expect(productionPolicy.rules).toEqual([
      { userAgent: '*', allow: '/', disallow: [...privateRobotPaths] },
    ]);
    expect(productionPolicy.host).toBe('https://www.zylora.example');
  });

  it('keeps the stable public sitemap useful when optional APIs are unavailable', async () => {
    vi.stubEnv('NEXT_PUBLIC_WEB_ORIGIN', 'https://www.zylora.example');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('API unavailable')));
    const entries = await sitemap();
    const urls = entries.map((entry) => entry.url);

    expect(urls).toContain('https://www.zylora.example/');
    expect(urls).toContain('https://www.zylora.example/ai-website-builder');
    expect(urls).toContain('https://www.zylora.example/solutions/small-business');
    expect(urls.some((url) => url.includes('/app/'))).toBe(false);
    expect(entries.every((entry) => entry.lastModified === undefined)).toBe(true);
  });

  it('escapes JSON-LD payloads before rendering them into script content', () => {
    expect(serializeJsonLd({ value: '</script><script>alert(1)</script>' })).not.toContain('<');
    expect(serializeJsonLd({ value: '</script>' })).toContain('\\u003c/script>');
  });
});
