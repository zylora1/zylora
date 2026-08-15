import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPageMetadata } from '@/lib/seo';

export const metadata: Metadata = createPageMetadata({
  title: 'Terms of Service',
  description:
    'Terms governing use of Zylora Website creation, publishing, and related product capabilities.',
  path: '/terms',
});
export default function TermsLayout({ children }: { children: ReactNode }) {
  return children;
}
