import type { Metadata } from 'next';

const DEFAULT_ORIGIN = 'http://localhost:3000';

export const siteIdentity = {
  name: 'Zylora',
  shortName: 'Zylora',
  description:
    'An AI website builder and Template-first website platform for small businesses, freelancers, and service teams.',
  locale: 'en_IN',
} as const;

export function siteOrigin() {
  return (process.env.NEXT_PUBLIC_WEB_ORIGIN ?? DEFAULT_ORIGIN).replace(/\/$/, '');
}

export function absoluteUrl(path = '/') {
  return new URL(path, `${siteOrigin()}/`).toString();
}

export function publicIndexingEnabled() {
  return process.env.NEXT_PUBLIC_SEARCH_INDEXING_ENABLED === 'true';
}

type PageMetadata = {
  title: string;
  description: string;
  path: string;
  image?: string;
  type?: 'website' | 'article';
  noIndex?: boolean;
  absoluteTitle?: boolean;
};

export function createPageMetadata({
  title,
  description,
  path,
  image = '/opengraph-image',
  type = 'website',
  noIndex = false,
  absoluteTitle = false,
}: PageMetadata): Metadata {
  const resolvedTitle = absoluteTitle ? { absolute: title } : title;
  return {
    title: resolvedTitle,
    description,
    alternates: { canonical: path },
    robots:
      noIndex || !publicIndexingEnabled()
        ? { index: false, follow: false, nocache: true }
        : {
            index: true,
            follow: true,
            googleBot: {
              index: true,
              follow: true,
              'max-image-preview': 'large',
              'max-snippet': -1,
              'max-video-preview': -1,
            },
          },
    openGraph: {
      type,
      siteName: siteIdentity.name,
      locale: siteIdentity.locale,
      url: path,
      title,
      description,
      images: [
        { url: image, width: 1200, height: 630, alt: `${siteIdentity.name} product preview` },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [image],
    },
  };
}

export function createPrivateMetadata(title: string, description: string): Metadata {
  return createPageMetadata({
    title,
    description,
    path: '/',
    noIndex: true,
  });
}

export function serializeJsonLd(value: unknown) {
  return JSON.stringify(value).replace(/</g, '\\u003c');
}
