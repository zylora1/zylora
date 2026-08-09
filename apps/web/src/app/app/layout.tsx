import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { PortalShell } from '@/components/portal-shell';

export const metadata: Metadata = {
  title: 'Workspace · Zylora',
  robots: { index: false, follow: false },
};

export default function UserWorkspaceLayout({ children }: { children: ReactNode }) {
  return <PortalShell>{children}</PortalShell>;
}
