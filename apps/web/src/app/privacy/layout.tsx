import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPageMetadata } from '@/lib/seo';

export const metadata: Metadata = createPageMetadata({
  title: 'Privacy Policy',
  description: 'How Zylora handles account, Website, billing, support, and product activity data.',
  path: '/privacy',
});
export default function PrivacyLayout({ children }: { children: ReactNode }) {
  return children;
}
