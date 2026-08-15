import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPrivateMetadata } from '@/lib/seo';

export const metadata: Metadata = createPrivateMetadata(
  'Create an account',
  'Create a private Zylora User account.',
);

export default function SignupLayout({ children }: { children: ReactNode }) {
  return children;
}
