import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import '@zylora/ui/tokens.css';
import './globals.css';
import './portal.css';

export const metadata: Metadata = {
  title: { default: 'Zylora · Your website, thoughtfully made', template: '%s · Zylora' },
  description: 'Choose an approved Template, customize it, and publish a Website you control.',
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
