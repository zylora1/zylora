import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPageMetadata } from '@/lib/seo';

export const metadata: Metadata = createPageMetadata({
  title: 'Website Building Journal',
  description:
    'Practical Zylora guides for shaping, publishing, and improving a business Website you own.',
  path: '/blog',
});

export default function BlogLayout({ children }: { children: ReactNode }) {
  return children;
}
