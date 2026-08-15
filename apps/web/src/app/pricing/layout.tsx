import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPageMetadata } from '@/lib/seo';

export const metadata: Metadata = createPageMetadata({
  title: 'Website Builder Pricing',
  description:
    'Compare Zylora monthly Website publishing plans and the capabilities each plan supports.',
  path: '/pricing',
});

export default function PricingLayout({ children }: { children: ReactNode }) {
  return children;
}
