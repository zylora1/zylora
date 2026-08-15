import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPrivateMetadata } from '@/lib/seo';

export const metadata: Metadata = createPrivateMetadata(
  'Recover account',
  'Request a private Zylora password reset.',
);

export default function ForgotPasswordLayout({ children }: { children: ReactNode }) {
  return children;
}
