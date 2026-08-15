import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { createPrivateMetadata } from '@/lib/seo';

export const metadata: Metadata = createPrivateMetadata(
  'Set a new password',
  'Complete a private Zylora password reset.',
);

export default function ResetPasswordLayout({ children }: { children: ReactNode }) {
  return children;
}
