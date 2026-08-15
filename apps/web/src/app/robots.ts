import type { MetadataRoute } from 'next';

import { siteOrigin } from '@/lib/seo';

export const privateRobotPaths = [
  '/app/',
  '/admin/',
  '/api/',
  '/login',
  '/signup',
  '/verify-email',
  '/forgot-password',
  '/reset-password',
  '/unsubscribe',
  '/health',
  '/dev/',
  '/*/preview',
] as const;

export default function robots(): MetadataRoute.Robots {
  const origin = siteOrigin();
  const indexingEnabled = process.env.NEXT_PUBLIC_SEARCH_INDEXING_ENABLED === 'true';

  return {
    rules: [
      {
        userAgent: '*',
        ...(indexingEnabled ? { allow: '/' } : {}),
        disallow: indexingEnabled ? [...privateRobotPaths] : ['/', ...privateRobotPaths],
      },
    ],
    sitemap: `${origin}/sitemap.xml`,
    ...(indexingEnabled ? { host: origin } : {}),
  };
}
