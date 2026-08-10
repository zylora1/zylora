import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import '@zylora/ui/tokens.css';
import './globals.css';
import './portal.css';

const origin = process.env.NEXT_PUBLIC_WEB_ORIGIN ?? 'http://localhost:3000';

export const metadata: Metadata = {
  metadataBase: new URL(origin),
  title: { default: 'Zylora | Professional websites, thoughtfully made', template: '%s | Zylora' },
  description:
    'Choose an approved Template, customize it manually or with AI, then publish, transfer, or export a Website you control.',
  robots: { index: true, follow: true },
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    siteName: 'Zylora',
    title: 'Zylora | Professional websites, thoughtfully made',
    description:
      'Choose an approved Template, customize it manually or with AI, then publish, transfer, or export.',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Zylora | Professional websites, thoughtfully made',
    description:
      'Choose an approved Template, customize it manually or with AI, then publish, transfer, or export.',
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
