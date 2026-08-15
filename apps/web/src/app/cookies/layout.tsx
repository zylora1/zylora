import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPageMetadata } from '@/lib/seo';

export const metadata: Metadata = createPageMetadata({
  title: 'Cookie Policy',
  description:
    'How Zylora uses essential session, security, preference, and product analytics data.',
  path: '/cookies',
});
export default function CookiesLayout({ children }: { children: ReactNode }) {
  return children;
}
