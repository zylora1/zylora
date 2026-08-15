import type { MetadataRoute } from 'next';

import { siteIdentity } from '@/lib/seo';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: siteIdentity.name,
    short_name: siteIdentity.shortName,
    description: siteIdentity.description,
    start_url: '/',
    display: 'standalone',
    background_color: '#070808',
    theme_color: '#070808',
    icons: [
      {
        src: '/icon.svg',
        sizes: 'any',
        type: 'image/svg+xml',
      },
    ],
  };
}
