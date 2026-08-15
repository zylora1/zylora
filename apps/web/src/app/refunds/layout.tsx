import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPageMetadata } from '@/lib/seo';

export const metadata: Metadata = createPageMetadata({
  title: 'Refunds and Cancellations',
  description:
    'Information about Zylora subscription cancellation, refund review, and help with a charge.',
  path: '/refunds',
});
export default function RefundsLayout({ children }: { children: ReactNode }) {
  return children;
}
