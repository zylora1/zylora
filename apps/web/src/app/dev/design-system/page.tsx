import { notFound } from 'next/navigation';

import { DesignSystemLab } from '@/components/design-system-lab';

export const dynamic = 'force-dynamic';

export default function DesignSystemPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <DesignSystemLab />;
}
