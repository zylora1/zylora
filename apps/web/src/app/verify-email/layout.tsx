import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPrivateMetadata } from '@/lib/seo';

export const metadata: Metadata = createPrivateMetadata(
  'Verify email',
  'Complete private Zylora account verification.',
);

export default function VerifyEmailLayout({ children }: { children: ReactNode }) {
  return children;
}
