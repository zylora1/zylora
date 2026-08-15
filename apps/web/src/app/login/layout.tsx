import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPrivateMetadata } from '@/lib/seo';

export const metadata: Metadata = createPrivateMetadata(
  'Sign in',
  'Sign in to the private Zylora User workspace.',
);

export default function LoginLayout({ children }: { children: ReactNode }) {
  return children;
}
