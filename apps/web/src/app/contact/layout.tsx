import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPageMetadata } from '@/lib/seo';

export const metadata: Metadata = createPageMetadata({
  title: 'Contact Zylora',
  description:
    'Contact the Zylora team about Website creation, publishing, a purchase, or a product workflow.',
  path: '/contact',
});

export default function ContactLayout({ children }: Readonly<{ children: ReactNode }>) {
  return children;
}
