import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';

import { AttributionCapture } from '@/components/attribution-capture';
import { MotionProvider } from '@/components/motion-provider';
import { publicIndexingEnabled, siteIdentity, siteOrigin } from '@/lib/seo';

import '@zylora/ui/tokens.css';
import './globals.css';
import './portal.css';

// Per-request CSP nonces require dynamic rendering; static output cannot receive a nonce safely.
export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  metadataBase: new URL(siteOrigin()),
  applicationName: siteIdentity.name,
  title: {
    default: 'Zylora — AI Website Builder for Small Businesses',
    template: '%s | Zylora',
  },
  description: siteIdentity.description,
  category: 'technology',
  referrer: 'origin-when-cross-origin',
  formatDetection: { email: false, address: false, telephone: false },
  robots: publicIndexingEnabled()
    ? { index: true, follow: true }
    : { index: false, follow: false, nocache: true },
  icons: { icon: '/icon.svg' },
  manifest: '/manifest.webmanifest',
  openGraph: {
    type: 'website',
    siteName: siteIdentity.name,
    locale: siteIdentity.locale,
    title: 'Zylora — AI Website Builder for Small Businesses',
    description: siteIdentity.description,
    images: [
      {
        url: '/opengraph-image',
        width: 1200,
        height: 630,
        alt: 'Zylora AI website builder and professional Template platform',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Zylora — AI Website Builder for Small Businesses',
    description: siteIdentity.description,
    images: ['/opengraph-image'],
  },
};

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#070808',
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AttributionCapture />
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}
