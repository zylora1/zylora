import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPrivateMetadata } from '@/lib/seo';

export const metadata: Metadata = createPrivateMetadata(
  'Email preferences',
  'Update private Zylora marketing email preferences.',
);

export default function UnsubscribeLayout({ children }: { children: ReactNode }) {
  return children;
}
