import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { PortalShell } from '@/components/portal-shell';

export const metadata: Metadata = {
  title: 'Super Admin · Zylora',
  robots: { index: false, follow: false },
};

export default function AdminWorkspaceLayout({ children }: { children: ReactNode }) {
  return <PortalShell admin>{children}</PortalShell>;
}
