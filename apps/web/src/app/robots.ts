import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  const origin = process.env.NEXT_PUBLIC_WEB_ORIGIN ?? 'http://localhost:3000';
  return {
    rules: [
      {
        userAgent: '*',
        allow: ['/', '/blog/', '/templates/'],
        disallow: ['/app/', '/admin/', '/api/'],
      },
    ],
    sitemap: `${origin}/sitemap.xml`,
  };
}
